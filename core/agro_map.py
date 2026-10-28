"""Optional OpenStreetMap agro-dealer discovery. Third-party, unverified listings."""
import json
import urllib.parse
import urllib.request

from .smartfarm import resolve_weather_location


def nearby_agrodealers(district_code, radius_m=20000, timeout=12):
    _, point = resolve_weather_location(district_code)
    lat, lon = float(point['latitude']), float(point['longitude'])
    radius_m = max(1000, min(int(radius_m), 30000))
    # Listings are crowdsourced. Search terms describe shops, not medical treatment advice.
    query = f'''[out:json][timeout:12];(
      nwr(around:{radius_m},{lat},{lon})[shop=agrarian];
      nwr(around:{radius_m},{lat},{lon})[shop=agricultural_supplies];
      nwr(around:{radius_m},{lat},{lon})[shop=trade][name~"agro|farm|seed|fertiliz",i];
      nwr(around:{radius_m},{lat},{lon})[name~"agrovet|agro.?dealer|agri.?input",i];
    );out center 40;'''
    request = urllib.request.Request('https://overpass-api.de/api/interpreter',
        data=urllib.parse.urlencode({'data':query}).encode(),
        headers={'User-Agent':'IhingaAI prototype agricultural directory/1.0'}, method='POST')
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        payload=json.load(resp)
    result=[]; seen=set()
    for item in payload.get('elements', []):
        tags=item.get('tags',{})
        name=tags.get('name')
        pos=item.get('center') or item
        p_lat,p_lon=pos.get('lat'),pos.get('lon')
        if not name or p_lat is None or p_lon is None:continue
        identity=(item.get('type'),item.get('id'))
        if identity in seen:continue
        seen.add(identity)
        result.append({'name':str(name)[:120],'latitude':float(p_lat),'longitude':float(p_lon),
                       'type':str(tags.get('shop') or tags.get('office') or 'listing')[:80],
                       'source':'OpenStreetMap / Overpass (unverified)'})
    return {'district':point['name'],'reference':(lat,lon),'shops':result}
