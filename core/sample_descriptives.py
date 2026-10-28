"""Validated, disclosure-controlled SAS 2025 *sample* descriptive rows.

This is NOT population estimation or official district production statistics.
No respondent identifiers, raw plot records, or sampling weight expansions appear.
"""
import csv
import math
from pathlib import Path

FIELDS = ('year','season','district_code','crop_code','sample_records',
          'records_with_harvest','distinct_sample_segments',
          'median_recorded_crop_area_ha','source')


def load_sample_descriptives(path):
    path = Path(path)
    if not path.is_file():
        return []
    seen=set()
    result=[]
    with path.open('r',encoding='utf-8-sig',newline='') as fh:
        reader=csv.DictReader(fh)
        if reader.fieldnames is None or any(f not in reader.fieldnames for f in FIELDS):
            raise ValueError('Survey descriptive CSV missing required columns')
        for rownum, r in enumerate(reader, start=2):
            try:
                year=int(r['year'])
                season=str(r['season']).strip().upper()
                district=str(r['district_code']).strip()
                crop=str(r['crop_code']).strip()
                n=int(r['sample_records'])
                harvested=int(r['records_with_harvest'])
                segments=int(r['distinct_sample_segments'])
                median=float(r['median_recorded_crop_area_ha'])
                source=str(r['source']).strip()
                if year!=2025 or season not in ('A','B','C'):
                    raise ValueError('Invalid survey year or season')
                if not district.isdecimal() or not crop.isdecimal():
                    raise ValueError('District/crop codes must be numeric')
                if not (n>=20 and 15<=harvested<=n and 5<=segments<=n):
                    raise ValueError('Unacceptable group size or missing data')
                if not (math.isfinite(median) and median>0):
                    raise ValueError('Nonpositive median crop area')
                if not source or len(source)>300:
                    raise ValueError('Missing source/provenance')
                key=(year,season,district,crop)
                if key in seen:
                    raise ValueError('Duplicate year-season-district-crop group')
                seen.add(key)
                result.append({'year':year,'season':season,'district_code':district,'crop_code':crop,
                               'sample_records':n,'records_with_harvest':harvested,
                               'distinct_sample_segments':segments,
                               'median_recorded_crop_area_ha':median,'source':source})
            except (ValueError,TypeError,KeyError) as ex:
                raise ValueError(f'Survey descriptive CSV row {rownum}: {ex}') from ex
    return result
