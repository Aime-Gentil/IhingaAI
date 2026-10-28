# Labels and display text. Kinyarwanda is a DRAFT pending native-speaker review.
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

LANGS = {"en": "English", "rw": "Kinyarwanda"}

CROPS = {
    "101": {"en": "Maize", "rw": "Ibigori", "en_s": "maize", "rw_s": "ibigori"},
    "106": {"en": "Bush bean", "rw": "Ibishyimbo bigufi", "en_s": "bush beans", "rw_s": "ibishyimbo bigufi"},
    "110": {"en": "Irish potato", "rw": "Ibirayi", "en_s": "Irish potatoes", "rw_s": "ibirayi"},
    "103": {"en": "Sorghum", "rw": "Amasaka", "en_s": "sorghum", "rw_s": "amasaka"},
    "107": {"en": "Climbing bean", "rw": "Ibishyimbo bishingirirwa", "en_s": "climbing beans", "rw_s": "ibishyimbo bishingirirwa"},
    "108": {"en": "Pea", "rw": "Amashaza", "en_s": "peas", "rw_s": "amashaza"},
    "111": {"en": "Sweet potato", "rw": "Ibijumba", "en_s": "sweet potatoes", "rw_s": "ibijumba"},
    "122": {"en": "Soybean", "rw": "Soya", "en_s": "soybeans", "rw_s": "soya"},
    "123": {"en": "Groundnut", "rw": "Ubunyobwa", "en_s": "groundnuts", "rw_s": "ubunyobwa"},
    "301": {"en": "Cooking banana", "rw": "Ibitoki byo guteka", "en_s": "cooking bananas", "rw_s": "ibitoki byo guteka"},
    "302": {"en": "Dessert banana", "rw": "Imineke", "en_s": "dessert bananas", "rw_s": "imineke"},
    "303": {"en": "Banana for beer", "rw": "Ibitoki by'urwagwa", "en_s": "beer bananas", "rw_s": "ibitoki by'urwagwa"},
    "304": {"en": "Coffee", "rw": "Ikawa", "en_s": "coffee", "rw_s": "ikawa"},
    "305": {"en": "Cassava", "rw": "Imyumbati", "en_s": "cassava", "rw_s": "imyumbati"},
}

SEASONS = {
    "A": {"en": "Season A", "rw": "Igihembwe A"},
    "B": {"en": "Season B", "rw": "Igihembwe B"},
    "C": {"en": "Season C", "rw": "Igihembwe C"},
}

FARMER_TYPES = {
    "1": {"en": "Small-scale farmer (individual)", "rw": "Umuhinzi muto (ku giti cye)"},
    "2": {"en": "Small-scale group (cooperative/association)", "rw": "Itsinda ry'abahinzi bato (koperative/ishyirahamwe)"},
    "3": {"en": "Large-scale farmer (individual)", "rw": "Umuhinzi munini (ku giti cye)"},
    "4": {"en": "Large-scale organisation (company/cooperative)", "rw": "Ikigo cy'ubuhinzi kinini (sosiyete/koperative)"},
}

TEXT = {
    "app_title": {"en": "IhingaAI – Harvest estimate", "rw": "IhingaAI – Igereranya ry'umusaruro"},
    "intro": {"en": "Enter your field details to see a likely harvest range based on 2025 national survey patterns.",
              "rw": "Andika amakuru y'umurima wawe urebe umusaruro ushoboka, hashingiwe ku bushakashatsi bw'igihugu bwo mu 2025."},
    "draft_rw": {"en": "", "rw": "Icyitonderwa: inyandiko z'Ikinyarwanda ziracyasuzumwa."},
    "crop": {"en": "Crop", "rw": "Igihingwa"},
    "other_crops_note": {"en": "Estimates are available for the crops listed. Other crops will be supported for field records soon.",
                         "rw": "Igereranya riboneka ku bihingwa biri ku rutonde. Ibindi bihingwa bizashyirwamo vuba mu kubika amakuru y'umurima."},
    "season": {"en": "Season", "rw": "Igihembwe cy'ihinga"},
    "district": {"en": "District", "rw": "Akarere"},
    "choose": {"en": "Choose…", "rw": "Hitamo…"},
    "farmer_type": {"en": "Who farms this plot?", "rw": "Ni nde uhinga uyu murima?"},
    "harvest_q": {"en": "Will you harvest this crop during this season?", "rw": "Uzasarura iki gihingwa muri iki gihembwe?"},
    "yes": {"en": "Yes", "rw": "Yego"},
    "no": {"en": "No", "rw": "Oya"},
    "area_unit": {"en": "Plot size unit", "rw": "Igipimo cy'ubuso"},
    "sqm": {"en": "Square metres (m²)", "rw": "Metero kare (m²)"},
    "ha": {"en": "Hectares (ha)", "rw": "Hegitari (ha)"},
    "area": {"en": "Total plot size (whole plot, all crops together)", "rw": "Ubuso bwose bw'umurima (ibihingwa byose hamwe)"},
    "area_help": {"en": "Measure the whole plot, even if other crops grow on it. 1 hectare = 10,000 m².",
                  "rw": "Pima umurima wose, n'iyo hari ibindi bihingwa biwuhinzeho. Hegitari 1 = m² 10,000."},
    "submit": {"en": "Estimate my harvest", "rw": "Gereranya umusaruro wanjye"},
    "missing": {"en": "Please choose a district and enter the plot size.", "rw": "Hitamo akarere kandi wandike ubuso bw'umurima."},
    "likely_range": {"en": "Likely harvest range", "rw": "Umusaruro ushoboka"},
    "low": {"en": "Lower end", "rw": "Hasi"},
    "typical": {"en": "Typical estimate", "rw": "Igereranya risanzwe"},
    "high": {"en": "Upper end", "rw": "Hejuru"},
    "range_sentence": {"en": "About {low} to {high} kg of {crop} this season.",
                       "rw": "Hafi ya {low} kugeza kuri {high} kg z'{crop} muri iki gihembwe."},
    "coverage": {"en": "When tested on 2025 survey plots, ranges like this contained the actual harvest about {n} times out of 10.",
                 "rw": "Mu igerageza ku mirima y'ubushakashatsi bwo mu 2025, imibare nk'iyi yarimo umusaruro nyawo hafi inshuro {n} kuri 10."},
    "guide": {"en": "This is a rough guide based on past survey patterns, not a guarantee. It does not show what any farming practice would change.",
              "rw": "Iri ni igereranya rishingiye ku byabaye mu bushakashatsi bwashize, si icyizere ntakuka. Ntirigaragaza icyo uburyo runaka bwo guhinga bwahindura."},
    "evidence_stronger": {"en": "Testing evidence: stronger", "rw": "Ibimenyetso by'igerageza: bikomeye"},
    "evidence_limited": {"en": "Testing evidence: limited", "rw": "Ibimenyetso by'igerageza: bike"},
    "status_outside_scope": {"en": "No estimate: this tool has only been tested for small-scale farmers. Large farms could not be estimated reliably from these details.",
                             "rw": "Nta gereranya: iki gikoresho cyageragejwe ku bahinzi bato gusa. Imirima minini ntiyashoboye kugereranywa neza hakoreshejwe aya makuru."},
    "status_unsupported_crop_season": {"en": "No estimate: this crop is not supported for this season.",
                                       "rw": "Nta gereranya: iki gihingwa ntigishyigikiwe muri iki gihembwe."},
    "status_outside_area_range": {"en": "No estimate: this plot is larger than any comparable plot in the 2025 survey.",
                                  "rw": "Nta gereranya: uyu murima urusha ubunini imirima yose isa nawo mu bushakashatsi bwo mu 2025."},
    "status_no_harvest_this_season": {"en": "No estimate: estimates for this crop only cover plots that will be harvested this season.",
                                      "rw": "Nta gereranya: igereranya ry'iki gihingwa rireba gusa imirima izasarurwa muri iki gihembwe."},
    "status_unsupported_district": {"en": "No estimate: this crop was not recorded in this district in the survey data.",
                                    "rw": "Nta gereranya: iki gihingwa nticyagaragaye muri aka karere mu makuru y'ubushakashatsi."},
    "status_invalid_input": {"en": "Please check the details you entered.", "rw": "Reba neza amakuru winjije."},
    "w_size": {"en": "Your plot size is unusual compared with survey plots, so this estimate is less reliable. Large plots tended to be underestimated.",
               "rw": "Ubuso bw'umurima wawe ntibusanzwe ugereranyije n'imirima y'ubushakashatsi, bityo iri gereranya ntiryizewe cyane. Imirima minini yakunze kugereranywa munsi y'umusaruro nyawo."},
    "w_season_c": {"en": "Season C estimates are based on few survey records.",
                   "rw": "Igereranya ry'Igihembwe C rishingiye ku makuru make y'ubushakashatsi."},
    "w_group": {"en": "Very few farmer groups were in the survey data, so this estimate is less certain.",
                "rw": "Amatsinda y'abahinzi yari make cyane mu makuru y'ubushakashatsi, bityo iri gereranya ntiryizewe cyane."},
    "w_maize_b": {"en": "Maize Season B estimates were less stable in testing.",
                  "rw": "Igereranya ry'ibigori mu Gihembwe B ntiryari rihamye mu igerageza."},
    "w_limited_evidence": {"en": "For this crop, the tool was only slightly better than a simple typical-plot estimate, so treat this as a very rough guide.",
                           "rw": "Kuri iki gihingwa, iki gikoresho cyarushije gato igereranya risanzwe ry'umurima, bityo ufate iri gereranya nk'icyerekezo gusa."},
    "w_perennial": {"en": "For this crop, the estimate is the harvest expected this season from an established plantation. Plant age is not taken into account.",
                    "rw": "Kuri iki gihingwa, igereranya ni umusaruro witezwe muri iki gihembwe uvuye ku murima umaze gukura. Imyaka y'ibihingwa ntiyitaweho."},
    "w_harvest_conditional": {"en": "This estimate assumes you harvest this crop this season.",
                              "rw": "Iri gereranya rishingiye ku kuba uzasarura iki gihingwa muri iki gihembwe."},
    "about_title": {"en": "About this estimate", "rw": "Ibyerekeye iri gereranya"},
    "about_body": {
        "en": "- Based on the 2025 NISR Seasonal Agricultural Survey (14 crops).\n"
              "- Uses only crop, season, district, who farms the plot and total plot size.\n"
              "- Plot size means the whole plot, not only the part with this crop.\n"
              "- Tested for small-scale farmers only.\n"
              "- It cannot predict crop failure, and it is not advice about fertiliser, irrigation or other practices.\n"
              "- Experimental prototype: an estimate can be far from the real harvest.",
        "rw": "- Rishingiye ku Bushakashatsi bw'Ibihembwe by'Ubuhinzi bwa NISR bwo mu 2025 (ibihingwa 14).\n"
              "- Rikoresha gusa igihingwa, igihembwe, akarere, uhinga umurima n'ubuso bwose bw'umurima.\n"
              "- Ubuso bw'umurima ni umurima wose, si igice gihinzeho iki gihingwa gusa.\n"
              "- Ryageragejwe ku bahinzi bato gusa.\n"
              "- Ntirishobora guteganya ko igihingwa kizarumba, kandi si inama ku ifumbire, kuhira cyangwa ubundi buryo bwo guhinga.\n"
              "- Ni igerageza: igereranya rishobora gutandukana cyane n'umusaruro nyawo.",
    },
}


def t(key, lang, **kw):
    entry = TEXT[key]
    s = entry.get(lang) or entry["en"]
    return s.format(**kw) if kw else s


def load_districts():
    with open(DATA / "district_labels.json", encoding="utf-8") as f:
        return json.load(f)
