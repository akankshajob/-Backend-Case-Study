"""
Name: Akanksha Job
Project: Inventory Management System for B2B SaaS (StockFlow)

This file contains a backend engineering case study covering:
1. Code Review & Debugging
2. Database Design
3. API Implementation (Low-Stock Alerts)

All non-executable text is written as comments for clarity.
"""

# ============================================================
# OVERVIEW
# ============================================================

# StockFlow is a B2B inventory management platform.
# Small businesses use it to track products across
# multiple warehouses and manage supplier relationships.


# ============================================================
# PART 1: CODE REVIEW & DEBUGGING
# ============================================================

# Original API Endpoint (written by previous intern)

"""
@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.json

    product = Product(
        name=data['name'],
        sku=data['sku'],
        price=data['price'],
        warehouse_id=data['warehouse_id']
    )

    db.session.add(product)
    db.session.commit()

    inventory = Inventory(
        product_id=product.id,
        warehouse_id=data['warehouse_id'],
        quantity=data['initial_quantity']
    )

    db.session.add(inventory)
    db.session.commit()

    return {"message": "Product created", "product_id": product.id}
"""
# ------------------------------------------------------------
# Problems Found in the Code
# ------------------------------------------------------------

# 1. No input validation
# 2. No error handling
# 3. Two separate database commits
# 4. No authorization or authentication
# 5. SKU uniqueness not enforced

# ------------------------------------------------------------
# Impact in Production
# ------------------------------------------------------------

# - APIs may fail due to invalid input
# - Duplicate SKUs can corrupt product data
# - Partial commits can break inventory consistency
# - Unauthorized access can compromise business data


# ------------------------------------------------------------
# Corrected Version with Fixes
# ------------------------------------------------------------

from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from flask import request

@app.route('/api/products', methods=['POST'])
def create_product():
    """
    Improved product creation API with validation,
    transaction safety, and error handling.
    """

    data = request.json or {}

    # 1. Input validation
    required_fields = ['name', 'sku', 'price', 'warehouse_id']
    for field in required_fields:
        if field not in data:
            return {"error": f"{field} is required"}, 400

    # 2. SKU uniqueness check
    if Product.query.filter_by(sku=data['sku']).first():
        return {"error": "SKU must be unique"}, 409

    # 3. Safe decimal price handling
    try:
        price = Decimal(str(data['price']))
    except:
        return {"error": "Invalid price format"}, 400

    # 4. Optional quantity validation
    quantity = data.get('initial_quantity', 0)
    if quantity < 0:
        return {"error": "Initial quantity cannot be negative"}, 400

    try:
        # 5. Single transaction for consistency
        with db.session.begin():
            product = Product(
                name=data['name'],
                sku=data['sku'],
                price=price
            )
            db.session.add(product)
            db.session.flush()  # get product.id

            inventory = Inventory(
                product_id=product.id,
                warehouse_id=data['warehouse_id'],
                quantity=quantity
            )
            db.session.add(inventory)

        return {"message": "Product created", "product_id": product.id}, 201

    except IntegrityError:
        db.session.rollback()
        return {"error": "Database error while creating product"}, 500


# ============================================================
# PART 2: DATABASE DESIGN
# ============================================================

# SQL Schema (documented as comments)

"""
CREATE TABLE companies (
    company_id SERIAL PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE warehouses (
    warehouse_id SERIAL PRIMARY KEY,
    company_id INT REFERENCES companies(company_id),
    location_name VARCHAR(100),
    address TEXT
);

CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    company_id INT REFERENCES companies(company_id),
    sku VARCHAR(50),
    product_name VARCHAR(255),
    price DECIMAL(10,2),
    is_bundle BOOLEAN DEFAULT FALSE,
    UNIQUE (company_id, sku)
);

CREATE TABLE inventory (
    product_id INT REFERENCES products(product_id),
    warehouse_id INT REFERENCES warehouses(warehouse_id),
    quantity INT CHECK (quantity >= 0),
    PRIMARY KEY (product_id, warehouse_id)
);

CREATE TABLE inventory_logs (
    log_id SERIAL PRIMARY KEY,
    product_id INT,
    warehouse_id INT,
    change_amount INT,
    reason VARCHAR(50),
    created_at TIMESTAMP
);

CREATE TABLE bundle_items (
    parent_id INT REFERENCES products(product_id),
    child_id INT REFERENCES products(product_id),
    quantity_required INT,
    PRIMARY KEY (parent_id, child_id)
);

CREATE TABLE suppliers (
    supplier_id SERIAL PRIMARY KEY,
    company_id INT REFERENCES companies(company_id),
    supplier_name VARCHAR(255)
);

CREATE TABLE supplier_products (
    supplier_id INT REFERENCES suppliers(supplier_id),
    product_id INT REFERENCES products(product_id),
    PRIMARY KEY (supplier_id, product_id)
);
"""

# Design Notes:
# - Companies own warehouses, products, and suppliers
# - Inventory enables multi-warehouse stock tracking
# - Inventory logs provide audit history
# - Bundles are self-referencing products
# - Suppliers provide multiple products


# ============================================================
# PART 3: API IMPLEMENTATION – LOW STOCK ALERTS
# ============================================================

# Business Rules:
# - Low stock threshold varies by product
# - Alert only products with recent sales activity
# - Must support multiple warehouses per company
# - Include supplier information for reordering

# Assumptions:
# - Each product has a low_stock_threshold field
# - Sales table exists with product_id, warehouse_id, and date
# - A product can have one or more suppliers (primary supplier returned)
# - Authentication is handled outside this endpoint

from datetime import datetime, timedelta

@app.route('/api/companies/<int:company_id>/alerts/low-stock', methods=['GET'])
def get_low_stock(company_id):
    """
    Returns low-stock alerts for a given company.
    Alerts are generated only for products that:
    - Are below the defined stock threshold
    - Have recent sales activity
    """

    # Define recent sales window (last 30 days)
    last_month = datetime.now() - timedelta(days=30)

    # Fetch products with inventory below threshold
    query = db.session.query(
        Product,
        Inventory,
        Warehouse,
        Supplier
    ).join(
        Inventory, Product.id == Inventory.product_id
    ).join(
        Warehouse, Inventory.warehouse_id == Warehouse.id
    ).join(
        SupplierProduct, SupplierProduct.product_id == Product.id
    ).join(
        Supplier, Supplier.id == SupplierProduct.supplier_id
    ).filter(
        Product.company_id == company_id,
        Inventory.quantity <= Product.low_stock_threshold
    )

    alerts = []

    for product, inventory, warehouse, supplier in query.all():

        # Check for recent sales activity
        has_sales = Sale.query.filter(
            Sale.product_id == product.id,
            Sale.warehouse_id == warehouse.id,
            Sale.date >= last_month
        ).first()

        # Skip products with no recent sales
        if not has_sales:
            continue

        # Calculate average daily sales (helper function assumed)
        daily_velocity = get_daily_sales_rate(product.id, warehouse.id)

        # Estimate days until stockout
        # If sales velocity is zero, use a safe fallback value
        days_left = int(inventory.quantity / daily_velocity) if daily_velocity > 0 else 99

        alerts.append({
            "product_id": product.id,
            "product_name": product.product_name,
            "sku": product.sku,
            "warehouse_id": warehouse.warehouse_id,
            "warehouse_name": warehouse.location_name,
            "current_stock": inventory.quantity,
            "threshold": product.low_stock_threshold,
            "days_until_stockout": days_left,
            "supplier": {
                "id": supplier.supplier_id,
                "name": supplier.supplier_name,
                "contact_email": supplier.contact_email
            }
        })

    return {
        "alerts": alerts,
        "total_alerts": len(alerts)
    }, 200


# ------------------------------------------------------------
# EDGE CASES HANDLED
# ------------------------------------------------------------

# 1. Products without recent sales are excluded to avoid noisy alerts
# 2. Division by zero is avoided when sales velocity is zero
# 3. Products in multiple warehouses are evaluated independently
# 4. Missing supplier information does not break the response
# 5. If no products are low on stock, an empty alerts list is returned


# ------------------------------------------------------------
# APPROACH EXPLANATION
# ------------------------------------------------------------

# - Inventory is filtered using product-specific low stock thresholds
# - Recent sales activity ensures alerts are business-relevant
# - Alerts are generated at warehouse level for operational accuracy
# - Days until stockout is estimated using average daily sales
# - Supplier details are included to support immediate reordering