# Arrow Flight & Browser Data Transport — Research Notes

## Arrow Flight RPC Wire Format

Arrow Flight is built on **gRPC over HTTP/2**, with message schemas defined in Protocol Buffers. The wire format has four distinct layers:

### Layer 1: gRPC framing
Standard HTTP/2 with gRPC length-prefix per message:
```
[1 byte: compression flag][4 bytes: message length][N bytes: protobuf body]
```

### Layer 2: Protobuf — `FlightData`
The core message carrying Arrow data. Notably, `data_body` has field tag 1000 (intentionally high) so implementations can locate and forward it without full protobuf parsing:
```protobuf
message FlightData {
  FlightDescriptor flight_descriptor = 1;  // only on first DoPut message
  bytes data_header = 2;                   // Flatbuffer IPC header
  bytes app_metadata = 3;                  // per-batch application metadata
  bytes data_body = 1000;                  // raw Arrow column buffers
}
```

### Layer 3: IPC message (inside `data_header` + `data_body`)
`data_header` contains a **Flatbuffer-encoded** Arrow IPC `Message` (not protobuf — Flatbuffers support zero-copy random-access reads without parsing):
```
[0xFFFFFFFF][metadata_size (4 bytes LE)][Flatbuffer Message][padding to 8B][body buffers]
```
The Flatbuffer header describes exact byte offsets and lengths of each column buffer within `data_body`, enabling zero-copy deserialization.

### Layer 4: Columnar buffer layout (inside `data_body`)
Per column, in depth-first schema order:
| Buffer | Contents |
|---|---|
| Validity bitmap | 1 bit/row; absent if null count = 0 |
| Offsets | `int32[]`/`int64[]` for variable-length types |
| Values | Raw fixed-width or var-len bytes |

All buffers are 8-byte aligned.

### Why Flatbuffers embedded in Protobuf?
Arrow IPC format predates Flight and was designed for shared memory/file use cases. Rather than re-encode metadata in protobuf, Flight carries the existing IPC format as an opaque `bytes` field. This means a Flight implementation can hand `data_header + data_body` directly to the Arrow IPC reader without translation. Each serialisation format does what it's best at: protobuf for control fields, Flatbuffers for zero-copy Arrow metadata.

### Streaming affordances
Arrow's IPC format is designed for streaming:
- Schema message comes once at the start; batches are self-contained thereafter
- Fixed-size prefix framing means no delimiter scanning — read 8 bytes, know exactly how much follows
- Flatbuffer headers allow column-selective access by offset arithmetic
- No row-group statistics (unlike Parquet) — optimised for full-scan throughput, not selective skipping

---

## JavaScript/TypeScript Client Status

**`apache-arrow` (npm)** handles the IPC/columnar format but **has no Flight client** — this gap has been open since at least 2022.

Third-party options are mostly **Flight SQL** (the SQL-query layer on top of Flight), not raw Flight RPC:

| Package | Notes |
|---|---|
| `@lakehouse-rs/flight-sql-client` | Node.js only; Rust core via napi-rs |
| `@lancedb/arrow-flight-sql-client` | Experimental |
| `@firetiger-oss/flight-sql-client` | TypeScript, Flight + Flight SQL |

For raw Flight RPC from JS/TS: generate a gRPC client from `Flight.proto` using `@grpc/grpc-js` + `@grpc/proto-loader` and handle IPC encoding/decoding with `apache-arrow`.

---

## Sending Arrow Data to the Browser

### Recommended: HTTP streaming + `apache-arrow`
Plain HTTP is the right transport for browsers. gRPC requires a proxy (e.g. Envoy) and has no official Arrow Flight JS client.

```js
import { RecordBatchReader, tableFromIPC } from "apache-arrow";

// Buffer entire response
const table = await tableFromIPC(fetch("/data"));

// Or stream batch-by-batch
const reader = await RecordBatchReader.from(fetch("/data"));
for await (const batch of reader) { /* process as it arrives */ }
```

Backend serves `Content-Type: application/vnd.apache.arrow.stream`. Works with any Arrow backend (Python/pyarrow, Rust/arrow-ipc, Go, Java).

### For bidirectional/upload
WebSocket — send raw Arrow IPC frames; `RecordBatchReader` can read from an async iterator fed by WebSocket messages.

---

## Returning Arrow + JSON Together

### Options evaluated

| Approach | Verdict |
|---|---|
| Separate URL field in JSON response | **Best for most cases** — simple, cache-friendly, no encoding overhead |
| Base64 `Bytes` scalar in GraphQL | OK for small blobs; ~33% size overhead, buffers entire blob |
| GraphQL `@defer` multipart | Built for JSON parts only; no framework support for binary parts |
| Custom `multipart/mixed` | Works but requires DIY client-side parser; no framework integration |

### Response headers for metadata
Header size limits make them unsuitable for anything beyond small scalar metadata:
- Nginx: ~8KB default
- Node.js: 16KB default
- Cloudflare: 128KB (increased Oct 2025)

### Multipart/mixed parsers (if pursued)
- [`@mjackson/multipart-parser`](https://www.npmjs.com/package/@mjackson/multipart-parser) — universal JS, web Streams API
- [`@slamb/multipart-stream`](https://www.npmjs.com/package/@slamb/multipart-stream) — WHATWG fetch-native

None have TanStack/React integration — all are low-level stream parsers requiring a custom wrapper.

---

## Architecture for Headless BI

### BFF vs parallel fetches
HTTP/2 multiplexes parallel requests over one connection — the old HTTP/1.1 waterfall problem is largely gone. RSCs and TanStack Query both favour granular parallel fetching over a single aggregating endpoint. A BFF still adds value for server-side fan-out, auth, caching, and query rewriting — particularly when the BFF→DB link is low-latency (same datacenter) and results can start streaming before all queries complete.

### React Server Components
RSCs render server-side and stream a **single chunked HTTP response** to the browser. Multiple data fetches fan out in parallel on the server; Suspense boundaries allow progressive rendering as each resolves. RSC payload is JSON-serializable only — **Arrow binary cannot be included**. This suggests a natural split:

- **RSC response**: report title, descriptions, chart configs, axis labels, filter values, panel layout
- **Browser-initiated parallel Arrow fetches**: one per data panel, starting as soon as RSC shell arrives

### TanStack Query implementation

```tsx
// Server (Next.js RSC) — prefetch config, seed client cache
await queryClient.prefetchQuery({
  queryKey: ["report", id],
  queryFn: () => fetchReportConfig(id),
});

// Client — config hits cache immediately, Arrow fetches start in parallel
async function fetchArrowTable(url: string) {
  const reader = await RecordBatchReader.from(fetch(url));
  return reader.readAll();
}

function ReportPage({ reportId }: { reportId: string }) {
  const { data: report } = useSuspenseQuery({
    queryKey: ["report", reportId],
    queryFn: () => fetch(`/api/report/${reportId}`).then(r => r.json()),
  });

  return (
    <>
      <h1>{report.title}</h1>
      {report.panels.map(panel => (
        <Suspense key={panel.id} fallback={<ChartSkeleton />}>
          <DataPanel panel={panel} />
        </Suspense>
      ))}
    </>
  );
}

function DataPanel({ panel }: { panel: Panel }) {
  const { data: table } = useSuspenseQuery({
    queryKey: ["arrow", panel.dataUrl],
    queryFn: () => fetchArrowTable(panel.dataUrl),
    staleTime: 30_000,
  });
  return <Chart table={table} config={panel.config} />;
}
```

Each panel wrapped in its own `<Suspense>` boundary renders progressively as Arrow fetches complete. The server prefetch of the report config eliminates the config→Arrow waterfall by seeding the TanStack cache before the client hydrates.
