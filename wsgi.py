from app import app, db, create_admin, init_db
import os

# Run these operations only once when the app is first deployed
if os.environ.get('RENDER_INITIAL_SETUP') == 'pending':
    with app.app_context():
        init_db()
        create_admin()
    os.environ['RENDER_INITIAL_SETUP'] = 'done'

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)