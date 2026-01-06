#Name - Akanksha Job
Inventory Management System for B2B SaaS
Overview
You're joining a team building "StockFlow" - a B2B inventory management platform. Small businesses use it to track products across multiple warehouses and manage supplier relationships.
Time Allocation
Take-Home Portion: 90 minutes maximum
Live Discussion: 30-45 minutes (scheduled separately)

Part 1: Code Review & Debugging (30 minutes)
A previous intern wrote this API endpoint for adding new products. Something is wrong - the code compiles but doesn't work as expected in production.
@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.json
    
    # Create new product
    product = Product(
        name=data['name'],
        sku=data['sku'],
        price=data['price'],
        warehouse_id=data['warehouse_id']
    )
    
    db.session.add(product)
    db.session.commit()
    
    # Update inventory count
    inventory = Inventory(
        product_id=product.id,
        warehouse_id=data['warehouse_id'],
        quantity=data['initial_quantity']
    )
    
    db.session.add(inventory)
    db.session.commit()
    
    return {"message": "Product created", "product_id": product.id}
ANSWER -
Problem found in Code -
No input validation 
No error handling
Two separate database commits
No authorization or authentication
SKU should have been unique 
Impact -
1. No Input Validation
The code directly accesses data['name'], data['sku'], data['price'], and data['warehouse_id'].
If any field is missing or invalid, the API will raise a runtime error.
There is no validation for optional fields like initial_quantity.
2. No Error Handling
There is no try-except block around database operations.
Any database failure (duplicate SKU, invalid foreign key, null value) will crash the API.
The user receives a generic server error with no clear message.
3. Two Separate Database Commits
db.session.commit() is called once after creating the product and again after creating inventory.
If inventory creation fails, the product is already saved.
This results in inconsistent data (product exists without inventory).
4. No Authorization or Authentication
The endpoint does not check if the request is from an authenticated or authorized user.
Any user can create products without permission checks.
This is risky for a B2B SaaS platform.
5. SKU Uniqueness Not Enforced
The code assigns sku=data['sku'] without checking if it already exists.
Since SKUs must be unique, duplicate products can be created.
This causes incorrect inventory tracking and reporting.
Overall Impact in Production
APIs may fail due to invalid input
Duplicate SKUs can corrupt product data
Partial commits can break inventory consistency
Unauthorized access can compromise business data


Provide Fixes: Corrected Version with Explanations
@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.json or {}
    # 1. Input validation
    required_fields = ['name', 'sku', 'price', 'warehouse_id']
    for field in required_fields:
        if field not in data:
            return {"error": f"{field} is required"}, 400
# 2. SKU uniqueness check
    if Product.query.filter_by(sku=data['sku']).first():
        return {"error": "SKU must be unique"}, 409

    # 3. Safe price handling
    try:
        price = Decimal(str(data['price']))
    except:
        return {"error": "Invalid price format"}, 400
# 4. Validate optional quantity
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
            db.session.flush()  # ensures product.id is available
            inventory = Inventory(
                product_id=product.id,
                warehouse_id=data['warehouse_id'],
                quantity=quantity
            )
            db.session.add(inventory)
        return {
            "message": "Product created successfully",
            "product_id": product.id
        }, 201
    # 6. Error handling
    except IntegrityError:
        db.session.rollback()
        return {"error": "Database error while creating product"}, 500
Explanation -
1. Added Input Validation
Ensures all required fields are present before processing.


Prevents runtime errors caused by missing data.
2. Enforced SKU Uniqueness
Checks if a product with the same SKU already exists.


Maintains platform-wide product consistency.
3. Safe Decimal Price Handling
Uses Decimal instead of raw values.


Prevents floating-point precision issues in pricing.
4. Handled Optional Fields Safely
initial_quantity is optional and defaults to 0.
Negative quantities are explicitly rejected.
5. Used a Single Database Transaction
Product and inventory are created together.
Prevents partial data in case of failure.
6. Added Proper Error Handling
Catches database integrity errors.
Returns meaningful error responses instead of crashing.

Part 2: Database Design (25 minutes)
Based on the requirements below, design a database schema. Note: These requirements are intentionally incomplete - you should identify what's missing.
Given Requirements:
Companies can have multiple warehouses
Products can be stored in multiple warehouses with different quantities
Track when inventory levels change
Suppliers provide products to companies
Some products might be "bundles" containing other products
Your Tasks:
Design Schema: Create tables with columns, data types, and relationships
Identify Gaps: List questions you'd ask the product team about missing requirements
Explain Decisions: Justify your design choices (indexes, constraints, etc.)
Format: Use any notation (SQL DDL, ERD, text description, etc.)
1. Companies
CREATE TABLE companies (
    company_id SERIAL PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
2. Warehouses (multiple per company)
CREATE TABLE warehouses (
    warehouse_id SERIAL PRIMARY KEY,
    company_id INT NOT NULL REFERENCES companies(company_id),
    location_name VARCHAR(100) NOT NULL,
    address TEXT
);
3. Products (company-scoped)
CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    company_id INT NOT NULL REFERENCES companies(company_id),
    sku VARCHAR(50) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    is_bundle BOOLEAN DEFAULT FALSE,
    UNIQUE (company_id, sku)
);
4. Inventory (products per warehouse)
CREATE TABLE inventory (
    product_id INT REFERENCES products(product_id),
    warehouse_id INT REFERENCES warehouses(warehouse_id),
    quantity INT DEFAULT 0 CHECK (quantity >= 0),
    PRIMARY KEY (product_id, warehouse_id)
);
5. Inventory logs (track quantity changes)
CREATE TABLE inventory_logs (
    log_id SERIAL PRIMARY KEY,
    product_id INT REFERENCES products(product_id),
    warehouse_id INT REFERENCES warehouses(warehouse_id),
    change_amount INT NOT NULL,
    reason VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
 6. Product bundles
CREATE TABLE bundle_items (
    parent_id INT REFERENCES products(product_id),
    child_id INT REFERENCES products(product_id),
    quantity_required INT DEFAULT 1,
    PRIMARY KEY (parent_id, child_id)
);
 7. Suppliers
CREATE TABLE suppliers (
    supplier_id SERIAL PRIMARY KEY,
    company_id INT REFERENCES companies(company_id),
    supplier_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
 8. Supplier–Product mapping
CREATE TABLE supplier_products (
    supplier_id INT REFERENCES suppliers(supplier_id),
    product_id INT REFERENCES products(product_id),
    PRIMARY KEY (supplier_id, product_id)
);
Schema Relationships 
One company – many warehouses, products, and suppliers
Products stored in multiple warehouses via inventory
Inventory logs track stock changes over time
Suppliers provide multiple products
Bundles are self-referencing products composed of other products
Missing Requirements / Questions
Should SKUs be globally unique or only per company?
Are negative quantities allowed (backorders)?
Can bundles contain other bundles?
Should inventory logs always require a reason?
Do suppliers need additional contract or pricing data?


Part 3: API Implementation (35 minutes)
Implement an endpoint that returns low-stock alerts for a company.
Business Rules (discovered through previous questions):
Low stock threshold varies by product type
Only alert for products with recent sales activity
Must handle multiple warehouses per company
Include supplier information for reordering
Endpoint Specification:
GET /api/companies/{company_id}/alerts/low-stock

Expected Response Format:
{
  "alerts": [
    {
      "product_id": 123,
      "product_name": "Widget A",
      "sku": "WID-001",
      "warehouse_id": 456,
      "warehouse_name": "Main Warehouse",
      "current_stock": 5,
      "threshold": 20,
      "days_until_stockout": 12,
      "supplier": {
        "id": 789,
        "name": "Supplier Corp",
        "contact_email": "orders@supplier.com"
      }
    }
  ],
  "total_alerts": 1
}

Your Tasks:
Write Implementation: Use any language/framework (Python/Flask, Node.js/Express, etc.)
Handle Edge Cases: Consider what could go wrong
Explain Approach: Add comments explaining your logic
Hints: You'll need to make assumptions about the database schema and business logic. Document these assumptions.
ANSWER-
@app.route('/api/companies/<int:company_id>/alerts/low-stock', methods=['GET'])
def get_low_stock(company_id):
    # Define recent sales window
    last_month = datetime.now() - timedelta(days=30)
    # Query products with low inventory
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
        if not has_sales:
            continue
        # Calculate average daily sales
        daily_velocity = get_daily_sales_rate(product.id, warehouse.id)
        # Estimate days until stockout
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
Edge Cases Handled
Products without recent sales are excluded from alerts.
Division by zero is avoided when sales velocity is zero.
Products in multiple warehouses are evaluated separately.
Missing supplier data does not break the response.
If no products are low on stock, an empty list is returned.
Approach Explanation
Inventory is filtered using product-specific low stock thresholds.
Recent sales activity is checked to avoid unnecessary alerts.
Alerts are generated at the warehouse level for accuracy.
Days until stockout is estimated using average daily sales.
Supplier information is included to support immediate reordering.








Submission Instructions
Create a document with your responses to all three parts
Include reasoning for each decision you made
List assumptions you had to make due to incomplete requirements
Submit within 90 minutes of receiving this case study
Be prepared to walk through your solutions in the live session

Live Session Topics (Preview)
During our video call, we'll discuss:
Your debugging approach and thought process
Database design trade-offs and scalability considerations
How you'd handle edge cases in your API implementation
Questions about missing requirements and how you'd gather more info
Alternative approaches you considered

Evaluation Criteria
Technical Skills:
Code quality and best practices
Database design principles
Understanding of API design
Problem-solving approach
Communication:
Ability to identify and ask about ambiguities
Clear explanation of technical decisions
Professional collaboration style
Business Understanding:
Recognition of real-world constraints
Consideration of user experience
Scalability and maintenance thinking

Note: This is designed to assess your current skill level and learning potential. We don't expect perfect solutions - we're more interested in your thought process and ability to work with incomplete information.


