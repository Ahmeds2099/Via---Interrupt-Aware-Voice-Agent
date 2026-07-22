"""Create deterministic PDF, CSV, and JSON files for Via's judge demo."""

import json
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "demo-data"


def create_pdf() -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        """Harbor View Residences - Property Brief

Unit A-204 is a two-bedroom apartment priced at $425,000.
It has 1,180 square feet, one parking space, and a south-facing balcony.
The monthly association fee is $310.
The property is available for inspection Monday to Saturday, 10 AM to 5 PM.
The uploaded brief does not contain mortgage approval or legal advice.""",
        fontsize=11,
    )
    document.save(OUTPUT / "real-estate-brief.pdf")
    document.close()


def create_csv() -> None:
    (OUTPUT / "property-listings.csv").write_text(
        "property_id,address,bedrooms,price,status\n"
        "HV-A204,Harbor View A-204,2,425000,Available\n"
        "HV-B110,Harbor View B-110,1,315000,Reserved\n"
        "GV-C302,Green Valley C-302,3,610000,Available\n",
        encoding="utf-8",
    )


def create_json() -> None:
    payload = {
        "development": "Harbor View Residences",
        "amenities": ["fitness center", "rooftop garden", "visitor parking"],
        "policies": {
            "pets": "Allowed with association registration",
            "short_term_rentals": "Not permitted",
        },
        "contact": {"inspection_hours": "Monday-Saturday, 10 AM-5 PM"},
    }
    (OUTPUT / "development-details.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    create_pdf()
    create_csv()
    create_json()
    print(f"Demo assets created in {OUTPUT}")
