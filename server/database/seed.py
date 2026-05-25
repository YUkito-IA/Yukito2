import json
from sqlalchemy.orm import Session
from .models import Pack, SessionLocal

def seed_test_pack():
    db = SessionLocal()
    # Check if we already have it
    pack = db.query(Pack).filter(Pack.game == "Mario Kart").first()
    if not pack:
        new_pack = Pack(
            game="Mario Kart",
            system="SNES",
            core="snes9x",
            max_players=4,
            version="1.0",
            rom_filename="mariokart.sfc",
            rom_hash="test_hash_1234",
            core_filename="snes9x.so"
        )
        db.add(new_pack)
        db.commit()
        print("Seeded Mario Kart pack in DB.")
    else:
        print("Pack already exists in DB.")
    db.close()

if __name__ == "__main__":
    seed_test_pack()
