"""
Script to safely delete all users and their Stripe subscriptions.

WARNING: This will:
1. Cancel all active Stripe subscriptions (users won't be charged anymore)
2. Delete all user accounts and their associated data
3. This action is IRREVERSIBLE

Run this script from the project root:
    python delete_all_users.py
"""

import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import stripe

# Add app to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.user import User
from app.models.subscription import Subscription
from app.core.config import settings

def delete_all_users():
    """Delete all users after canceling their Stripe subscriptions."""

    # Initialize Stripe
    stripe.api_key = settings.STRIPE_API_KEY

    # Create database session
    SQLALCHEMY_DATABASE_URL = (
        f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        # Get all users
        users = db.query(User).all()
        total_users = len(users)

        print(f"\n{'='*60}")
        print(f"Found {total_users} users to delete")
        print(f"{'='*60}\n")

        if total_users == 0:
            print("No users found. Database is already clean.")
            return

        # Confirm deletion
        confirm = input(f"Are you sure you want to delete ALL {total_users} users? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Deletion canceled.")
            return

        deleted_count = 0
        stripe_canceled_count = 0
        stripe_errors = []

        for user in users:
            print(f"\nProcessing user: {user.email} (ID: {user.id})")

            # Get user's subscription
            subscription = db.query(Subscription).filter(
                Subscription.user_id == user.id
            ).first()

            # Cancel Stripe subscription if it exists
            if subscription and subscription.stripe_subscription_id:
                try:
                    print(f"  → Canceling Stripe subscription: {subscription.stripe_subscription_id}")
                    stripe.Subscription.delete(subscription.stripe_subscription_id)
                    stripe_canceled_count += 1
                    print(f"  ✓ Stripe subscription canceled")
                except stripe.error.StripeError as e:
                    error_msg = f"User {user.email}: {str(e)}"
                    stripe_errors.append(error_msg)
                    print(f"  ✗ Stripe error: {e}")
                except Exception as e:
                    error_msg = f"User {user.email}: {str(e)}"
                    stripe_errors.append(error_msg)
                    print(f"  ✗ Error: {e}")
            elif subscription and subscription.stripe_customer_id:
                print(f"  → User has Stripe customer ID but no active subscription")
            else:
                print(f"  → No Stripe subscription to cancel")

            # Delete user (cascade will delete subscription and other related data)
            db.delete(user)
            deleted_count += 1
            print(f"  ✓ User deleted from database")

        # Commit all deletions
        db.commit()

        # Print summary
        print(f"\n{'='*60}")
        print(f"DELETION SUMMARY")
        print(f"{'='*60}")
        print(f"Users deleted: {deleted_count}")
        print(f"Stripe subscriptions canceled: {stripe_canceled_count}")

        if stripe_errors:
            print(f"\nStripe errors encountered: {len(stripe_errors)}")
            for error in stripe_errors:
                print(f"  - {error}")
            print("\nNote: Users were still deleted from database even if Stripe cancellation failed.")
            print("You may need to manually cancel these subscriptions in the Stripe dashboard.")
        else:
            print(f"\n✓ All operations completed successfully!")

        print(f"{'='*60}\n")

    except Exception as e:
        db.rollback()
        print(f"\n✗ Error during deletion: {e}")
        print("Database changes have been rolled back.")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    delete_all_users()
