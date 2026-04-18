Configuration file reference
============================

Semolina reads connection settings from a TOML file, by default
``.semolina.toml`` in the current directory.

File location
-------------

:py:func:`~semolina.pool_from_config` looks for ``.semolina.toml`` in the
working directory. Pass a different path with the ``config_path`` argument:

.. code-block:: python

   pool, dialect = pool_from_config(
       config_path="config/warehouse.toml"
   )


File structure
--------------

Each named connection lives under ``[connections.<name>]``. The ``type`` field
is required and determines which backend fields are available.

.. code-block:: toml

   [connections.default]
   type = "snowflake"
   account = "xy12345.us-east-1"
   user = "alice"
   password = "s3cret"
   database = "ANALYTICS"
   warehouse = "COMPUTE_WH"

   [connections.analytics]
   type = "databricks"
   host = "adb-123456.azuredatabricks.net"
   http_path = "/sql/1.0/warehouses/abc123"
   token = "dapi..."
   catalog = "main"

Use ``pool_from_config(connection="analytics")`` to select a connection by
name; the default is ``"default"``.


Common fields
~~~~~~~~~~~~~

These fields are accepted by all connection types:

``type`` *string, required*
   Backend identifier. One of ``"snowflake"`` or ``"databricks"``.

``pool_size`` *integer, default 5*
   Number of connections to keep in the pool.

``max_overflow`` *integer, default 3*
   Extra connections allowed beyond ``pool_size`` under load.

``timeout`` *integer, default 30*
   Seconds to wait for a connection from the pool before raising.

``recycle`` *integer, default 3600*
   Seconds after which a connection is recycled (closed and replaced).


.. tab-set::
   :sync-group: warehouse

   .. tab-item:: Snowflake
      :sync: snowflake

      ``account`` *string*
         Snowflake account identifier (e.g. ``xy12345.us-east-1``).

      ``user`` *string*
         Username.

      ``password`` *string*
         Password for basic authentication.

      ``database`` *string*
         Default database.

      ``schema`` *string*
         Default schema.

      ``warehouse`` *string*
         Snowflake virtual warehouse.

      ``role`` *string*
         Snowflake role.

      ``region`` *string*
         Snowflake region, if not embedded in the account identifier.

      ``host`` *string*
         Explicit hostname (alternative to account-derived URI).

      ``port`` *integer*
         Connection port.

      ``protocol`` *string*
         ``"http"`` or ``"https"``.

      **Authentication**

      ``auth_type`` *string*
         Authentication method. One of ``auth_jwt``, ``auth_ext_browser``,
         ``auth_oauth``, ``auth_mfa``, ``auth_okta``, ``auth_pat``,
         ``auth_wif``. Omit for basic (user/password) authentication.

      ``private_key_path`` *string*
         File path to a PKCS1 or PKCS8 private key. Mutually exclusive with
         ``private_key_pem``.

      ``private_key_pem`` *string*
         Inline PEM-encoded PKCS8 private key. Mutually exclusive with
         ``private_key_path``.

      ``private_key_passphrase`` *string*
         Passphrase to decrypt an encrypted PKCS8 key.

      ``jwt_expire_timeout`` *string*
         JWT expiry duration (e.g. ``"300ms"``, ``"1m30s"``).

      ``oauth_token`` *string*
         Bearer token for ``auth_oauth``.

      ``okta_url`` *string*
         Okta server URL, required when ``auth_type = "auth_okta"``.

      ``identity_provider`` *string*
         Identity provider for ``auth_wif``.

      **Timeouts and behaviour**

      ``login_timeout`` *string*
         Login retry timeout duration.

      ``request_timeout`` *string*
         Request retry timeout duration.

      ``client_timeout`` *string*
         Network roundtrip timeout duration.

      ``tls_skip_verify`` *boolean, default false*
         Disable TLS certificate verification.

      ``ocsp_fail_open_mode`` *boolean, default true*
         Allow connection when OCSP check fails.

      ``keep_session_alive`` *boolean, default false*
         Prevent session expiry during long operations.

      ``app_name`` *string*
         Application identifier sent to Snowflake.

      ``disable_telemetry`` *boolean, default false*
         Disable Snowflake usage telemetry.

      ``cache_mfa_token`` *boolean, default false*
         Cache MFA token for subsequent connections.

      ``store_temp_creds`` *boolean, default false*
         Cache ID token for SSO.

   .. tab-item:: Databricks
      :sync: databricks

      Databricks connections can be configured in two ways: a full URI, or
      decomposed fields. Use one or the other, not both.

      **URI mode**

      ``uri`` *string*
         Full connection string:
         ``databricks://token:<token>@<host>:443/<http-path>``.

      **Decomposed mode**

      ``host`` *string*
         Workspace hostname (e.g. ``adb-123456.azuredatabricks.net``).

      ``http_path`` *string*
         SQL warehouse HTTP path (e.g. ``/sql/1.0/warehouses/abc123``).

      ``token`` *string*
         Personal access token.

      **Common fields**

      ``catalog`` *string*
         Default Unity Catalog.

      ``schema`` *string*
         Default schema.

      **OAuth authentication**

      ``auth_type`` *string*
         OAuth auth type. One of ``"OAuthU2M"`` (browser-based) or
         ``"OAuthM2M"`` (service principal). Omit for PAT authentication.

      ``client_id`` *string*
         OAuth M2M service principal client ID.

      ``client_secret`` *string*
         OAuth M2M service principal client secret.


See also
--------

- :doc:`/tutorials/installation` -- set up your first ``.semolina.toml``
- :doc:`/how-to/backends/overview` -- choose and configure a backend
- :doc:`/how-to/connection-pools` -- connection pool tuning
- :py:func:`~semolina.pool_from_config` -- API reference
