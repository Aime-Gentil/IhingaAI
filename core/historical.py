"""Separately validated aggregate historical statistics (never farmer accounts)."""
from pathlib import Path
import csv
import math

EXPECTED = ('year','season','district_code','crop_code','area_ha','production_kg','source')


def load_benchmarks(path):
    """Read user-provided, aggregate CSV and reject ambiguous or unsafe records."""
    path = Path(path)
    if not path.is_file():
        return []
    with path.open(encoding='utf-8-sig', newline='') as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames or any(k not in reader.fieldnames for k in EXPECTED):
            raise ValueError('Historical CSV missing required columns: ' + ', '.join(EXPECTED))
        rows=[]
        unique=set()
        for index, row in enumerate(reader, start=2):
            try:
                year=int(row['year'])
                season=row['season'].strip().upper()
                district=row['district_code'].strip()
                crop=row['crop_code'].strip()
                area=float(row['area_ha'])
                production=float(row['production_kg'])
                source=row['source'].strip()
                if not 2000 <= year <= 2100 or season not in ('A','B','C'):
                    raise ValueError('Invalid year or season')
                if not district or not crop or not source or len(source)>300:
                    raise ValueError('Missing crop, district, or source')
                if not (math.isfinite(area) and math.isfinite(production)) or area<=0 or production<0:
                    raise ValueError('Invalid area or production')
                key=(year,season,district,crop)
                if key in unique:raise ValueError('Duplicate crop-district-season-year record')
                unique.add(key)
                rows.append({'year':year,'season':season,'district_code':district,'crop_code':crop,
                             'area_ha':area,'production_kg':production,'yield_kg_ha':production/area,'source':source})
            except (ValueError, TypeError, KeyError) as exc:
                raise ValueError(f'Historical CSV row {index}: {exc}') from exc
        return rows
