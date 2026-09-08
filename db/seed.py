import argparse

from sqlmodel import Session, delete, select

from db.db import engine
from db.fixture import sample_markers
from db.models import Address, Marker


def seed(force: bool = False) -> None:
    with Session(engine) as session:
        if force:
            session.exec(delete(Marker))
            session.exec(delete(Address))
            print("Cleared existing markers and addresses.")
        elif session.exec(select(Marker)).first():
            print("Markers already exist — nothing to do. Use --force to reload.")
            return

        for fixture in sample_markers:
            address = Address(**fixture.address.model_dump(exclude={"id", "created_at"}))
            session.add(
                Marker(
                    latitude=fixture.latitude,
                    longitude=fixture.longitude,
                    title=fixture.title,
                    description=fixture.description,
                    category=fixture.category,
                    urgency=fixture.urgency,
                    status=fixture.status,
                    address=address,
                )
            )

        session.commit()
        print(f"Seeded {len(sample_markers)} markers.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load fixture markers into the database.")
    parser.add_argument("--force", action="store_true", help="delete existing rows first")
    seed(force=parser.parse_args().force)
