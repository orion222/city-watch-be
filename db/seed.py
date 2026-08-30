from sqlmodel import Session, select

from db.db import engine
from db.fixture import sample_markers
from db.models import Address, Marker


def seed() -> None:
    # Create initial data if tables are empty
    with Session(engine) as session:
        # Check if markers already exist
        existing_markers = session.exec(select(Marker)).first()
        if not existing_markers:
            print("Creating sample data from fixtures...")

            # Extract and create addresses first, then markers
            for fixture_marker in sample_markers:
                # Create address from fixture
                address_data = fixture_marker.address
                new_address = Address(
                    street=address_data.street,
                    city=address_data.city,
                    state=address_data.state,
                    postal_code=address_data.postal_code,
                    country=address_data.country
                )
                session.add(new_address)
                session.commit()
                session.refresh(new_address)

                # Create marker without nested address
                new_marker = Marker(
                    position=fixture_marker.position,
                    description=fixture_marker.description,
                    title=fixture_marker.title,
                    category=fixture_marker.category,
                    urgency=fixture_marker.urgency,
                    status=fixture_marker.status,
                    address_id=new_address.id  # Link to created address
                )
                session.add(new_marker)

            session.commit()
            print("Database initialized with sample marker data from fixtures")


if __name__ == "__main__":
    seed()
