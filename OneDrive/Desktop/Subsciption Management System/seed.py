from app import app, db, Product, Plan

with app.app_context():
    print("Connecting to database...")
    
    # Delete existing products and plans to start fresh
    Plan.query.delete()
    Product.query.delete()
    db.session.commit()

    mock_plans = [
        {"name": "Netflix Premium", "price": 649.0},
        {"name": "Spotify Premium", "price": 119.0},
        {"name": "YouTube Premium", "price": 129.0},
        {"name": "Meta Verified", "price": 699.0},
        {"name": "Amazon Prime", "price": 299.0},
        {"name": "Disney+ Hotstar", "price": 299.0},
        {"name": "Adobe Creative Cloud", "price": 1675.0},
        {"name": "Canva Pro", "price": 500.0},
        {"name": "ChatGPT Plus", "price": 1999.0},
        {"name": "Microsoft 365", "price": 489.0},
        {"name": "Apple Music", "price": 99.0},
        {"name": "LinkedIn Premium", "price": 1200.0},
        {"name": "Zee5 Premium", "price": 299.0},
        {"name": "SonyLIV Premium", "price": 299.0},
        {"name": "Coursera Plus", "price": 4000.0}
    ]
    
    for mp in mock_plans:
        prod = Product(name=mp["name"], sales_price=mp["price"], cost_price=mp["price"]*0.6)
        db.session.add(prod)
        db.session.commit()
        
        plan = Plan(product_id=prod.id, billing_period="monthly", price=mp["price"])
        db.session.add(plan)
        db.session.commit()
        
    print("Success! Marketplace seeded with 15+ products.")