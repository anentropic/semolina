"""
Realistic fixture data for jaffle-shop semantic view tests.

Provides type-accurate test data matching the structure of dbt-jaffle-shop semantic views.
Data includes edge cases (nulls, extremes) and variety (food/drink orders, customer types,
price ranges) to validate query logic and SQL generation.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

# Orders fixture data - 12 order records with variety of scenarios
orders_data: list[dict[str, Any]] = [
    # Food orders
    {
        "order_total": Decimal("45.50"),
        "order_count": 1,
        "tax_paid": Decimal("3.64"),
        "order_cost": Decimal("22.75"),
        "ordered_at": datetime(2024, 1, 15, 10, 30, 0),
        "order_total_dim": Decimal("45.50"),
        "is_food_order": True,
        "is_drink_order": False,
        "customer_order_number": 1,
    },
    {
        "order_total": Decimal("78.25"),
        "order_count": 1,
        "tax_paid": Decimal("6.26"),
        "order_cost": Decimal("39.13"),
        "ordered_at": datetime(2024, 3, 22, 14, 15, 0),
        "order_total_dim": Decimal("78.25"),
        "is_food_order": True,
        "is_drink_order": False,
        "customer_order_number": 2,
    },
    {
        "order_total": Decimal("92.00"),
        "order_count": 1,
        "tax_paid": Decimal("7.36"),
        "order_cost": Decimal("46.00"),
        "ordered_at": datetime(2024, 6, 10, 18, 45, 0),
        "order_total_dim": Decimal("92.00"),
        "is_food_order": True,
        "is_drink_order": False,
        "customer_order_number": 5,
    },
    # Drink orders
    {
        "order_total": Decimal("18.50"),
        "order_count": 1,
        "tax_paid": Decimal("1.48"),
        "order_cost": Decimal("9.25"),
        "ordered_at": datetime(2024, 2, 5, 8, 0, 0),
        "order_total_dim": Decimal("18.50"),
        "is_food_order": False,
        "is_drink_order": True,
        "customer_order_number": 1,
    },
    {
        "order_total": Decimal("24.75"),
        "order_count": 1,
        "tax_paid": Decimal("1.98"),
        "order_cost": Decimal("12.38"),
        "ordered_at": datetime(2024, 4, 18, 9, 30, 0),
        "order_total_dim": Decimal("24.75"),
        "is_food_order": False,
        "is_drink_order": True,
        "customer_order_number": 3,
    },
    # Mixed orders (both food and drink)
    {
        "order_total": Decimal("65.30"),
        "order_count": 1,
        "tax_paid": Decimal("5.22"),
        "order_cost": Decimal("32.65"),
        "ordered_at": datetime(2024, 5, 8, 12, 0, 0),
        "order_total_dim": Decimal("65.30"),
        "is_food_order": True,
        "is_drink_order": True,
        "customer_order_number": 4,
    },
    {
        "order_total": Decimal("54.90"),
        "order_count": 1,
        "tax_paid": Decimal("4.39"),
        "order_cost": Decimal("27.45"),
        "ordered_at": datetime(2024, 7, 20, 19, 15, 0),
        "order_total_dim": Decimal("54.90"),
        "is_food_order": True,
        "is_drink_order": True,
        "customer_order_number": 6,
    },
    # Edge cases - minimum order
    {
        "order_total": Decimal("12.00"),
        "order_count": 1,
        "tax_paid": Decimal("0.96"),
        "order_cost": Decimal("6.00"),
        "ordered_at": datetime(2024, 8, 3, 7, 45, 0),
        "order_total_dim": Decimal("12.00"),
        "is_food_order": False,
        "is_drink_order": True,
        "customer_order_number": 1,
    },
    # Edge cases - maximum order
    {
        "order_total": Decimal("125.80"),
        "order_count": 1,
        "tax_paid": Decimal("10.06"),
        "order_cost": Decimal("62.90"),
        "ordered_at": datetime(2024, 9, 12, 20, 30, 0),
        "order_total_dim": Decimal("125.80"),
        "is_food_order": True,
        "is_drink_order": True,
        "customer_order_number": 7,
    },
    # Additional variety
    {
        "order_total": Decimal("38.40"),
        "order_count": 1,
        "tax_paid": Decimal("3.07"),
        "order_cost": Decimal("19.20"),
        "ordered_at": datetime(2024, 10, 25, 11, 20, 0),
        "order_total_dim": Decimal("38.40"),
        "is_food_order": True,
        "is_drink_order": False,
        "customer_order_number": 2,
    },
    {
        "order_total": Decimal("71.15"),
        "order_count": 1,
        "tax_paid": Decimal("5.69"),
        "order_cost": Decimal("35.58"),
        "ordered_at": datetime(2024, 11, 8, 17, 0, 0),
        "order_total_dim": Decimal("71.15"),
        "is_food_order": True,
        "is_drink_order": True,
        "customer_order_number": 8,
    },
    {
        "order_total": Decimal("29.99"),
        "order_count": 1,
        "tax_paid": Decimal("2.40"),
        "order_cost": Decimal("15.00"),
        "ordered_at": datetime(2024, 12, 14, 13, 45, 0),
        "order_total_dim": Decimal("29.99"),
        "is_food_order": False,
        "is_drink_order": True,
        "customer_order_number": 4,
    },
]

# Customers fixture data - 6 customer records with variety
customers_data: list[dict[str, Any]] = [
    # New customer (1 order)
    {
        "customers": 1,
        "count_lifetime_orders": 1,
        "lifetime_spend_pretax": Decimal("41.86"),
        "lifetime_spend": Decimal("45.50"),
        "customer_name": "Alice Anderson",
        "customer_type": "new",
        "first_ordered_at": datetime(2024, 1, 15, 10, 30, 0),
        "last_ordered_at": datetime(2024, 1, 15, 10, 30, 0),
    },
    # Regular customer (5 orders)
    {
        "customers": 1,
        "count_lifetime_orders": 5,
        "lifetime_spend_pretax": Decimal("302.45"),
        "lifetime_spend": Decimal("328.64"),
        "customer_name": "Bob Baker",
        "customer_type": "regular",
        "first_ordered_at": datetime(2024, 2, 5, 8, 0, 0),
        "last_ordered_at": datetime(2024, 10, 25, 11, 20, 0),
    },
    # VIP customer (10 orders)
    {
        "customers": 1,
        "count_lifetime_orders": 10,
        "lifetime_spend_pretax": Decimal("625.80"),
        "lifetime_spend": Decimal("680.06"),
        "customer_name": "Charlie Chen",
        "customer_type": "vip",
        "first_ordered_at": datetime(2024, 3, 22, 14, 15, 0),
        "last_ordered_at": datetime(2024, 12, 14, 13, 45, 0),
    },
    # Active customer (8 orders)
    {
        "customers": 1,
        "count_lifetime_orders": 8,
        "lifetime_spend_pretax": Decimal("487.32"),
        "lifetime_spend": Decimal("529.56"),
        "customer_name": "Diana Davis",
        "customer_type": "regular",
        "first_ordered_at": datetime(2024, 4, 18, 9, 30, 0),
        "last_ordered_at": datetime(2024, 11, 8, 17, 0, 0),
    },
    # Super VIP customer (25 orders)
    {
        "customers": 1,
        "count_lifetime_orders": 25,
        "lifetime_spend_pretax": Decimal("1543.21"),
        "lifetime_spend": Decimal("1676.89"),
        "customer_name": "Eve Ellison",
        "customer_type": "vip",
        "first_ordered_at": datetime(2024, 5, 8, 12, 0, 0),
        "last_ordered_at": datetime(2024, 12, 20, 16, 30, 0),
    },
    # Edge case - customer with no orders (never ordered)
    {
        "customers": 1,
        "count_lifetime_orders": 0,
        "lifetime_spend_pretax": Decimal("0.00"),
        "lifetime_spend": Decimal("0.00"),
        "customer_name": "Frank Foster",
        "customer_type": "prospect",
        "first_ordered_at": datetime(2024, 6, 1, 0, 0, 0),
        "last_ordered_at": None,  # Edge case - no orders yet
    },
]

# Products fixture data - 10 product records with variety
products_data: list[dict[str, Any]] = [
    # Food items
    {
        "product_name": "Classic Burger",
        "product_type": "food",
        "product_description": "Juicy beef burger with lettuce, tomato, and special sauce",
        "is_food_item": True,
        "is_drink_item": False,
        "product_price": Decimal("12.99"),
    },
    {
        "product_name": "Margherita Pizza",
        "product_type": "food",
        "product_description": "Traditional pizza with mozzarella, basil, and tomato sauce",
        "is_food_item": True,
        "is_drink_item": False,
        "product_price": Decimal("15.50"),
    },
    {
        "product_name": "Caesar Salad",
        "product_type": "food",
        "product_description": "Crisp romaine with parmesan, croutons, and Caesar dressing",
        "is_food_item": True,
        "is_drink_item": False,
        "product_price": Decimal("10.99"),
    },
    {
        "product_name": "Chicken Wings",
        "product_type": "food",
        "product_description": "Spicy buffalo wings with ranch dressing",
        "is_food_item": True,
        "is_drink_item": False,
        "product_price": Decimal("13.75"),
    },
    # Drink items
    {
        "product_name": "Craft IPA",
        "product_type": "drink",
        "product_description": "Local craft IPA with citrus notes",
        "is_food_item": False,
        "is_drink_item": True,
        "product_price": Decimal("7.50"),
    },
    {
        "product_name": "Fresh Lemonade",
        "product_type": "drink",
        "product_description": "Freshly squeezed lemonade with mint",
        "is_food_item": False,
        "is_drink_item": True,
        "product_price": Decimal("4.50"),
    },
    {
        "product_name": "Cappuccino",
        "product_type": "drink",
        "product_description": "Espresso with steamed milk and foam",
        "is_food_item": False,
        "is_drink_item": True,
        "product_price": Decimal("5.25"),
    },
    {
        "product_name": "Red Wine Glass",
        "product_type": "drink",
        "product_description": "Premium Cabernet Sauvignon",
        "is_food_item": False,
        "is_drink_item": True,
        "product_price": Decimal("9.00"),
    },
    # Edge cases - price extremes
    {
        "product_name": "Side of Fries",
        "product_type": "food",
        "product_description": "Crispy golden fries with sea salt",
        "is_food_item": True,
        "is_drink_item": False,
        "product_price": Decimal("5.00"),  # Minimum price
    },
    {
        "product_name": "Steak Dinner",
        "product_type": "food",
        "product_description": "Premium ribeye with roasted vegetables and mashed potatoes",
        "is_food_item": True,
        "is_drink_item": False,
        "product_price": Decimal("28.99"),  # Maximum price
    },
]
