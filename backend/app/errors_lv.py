"""Robot error codes translated to plain Latvian with a next step.

Codes come from deebot-client's ``ERROR_CODES`` table (deebot_client/const.py).
That table is community-maintained and incomplete. Unknown codes get a generic
message and keep their number, so nobody is left guessing.
"""

from __future__ import annotations

from .models import ErrorInfo

# Codes that mean "no problem" or are informational notices, not faults.
NO_ERROR_CODES = frozenset({0, 100, 1021, 1061, 1071, 1094})

_STUCK = (
    "Robots ir iestrēdzis",
    "Robots nevar pakustēties no vietas.",
    "Atrodiet robotu un atbrīvojiet to. Pēc tam spiediet „Turpināt”.",
)
_OFF_FLOOR = (
    "Robots ir pacelts no grīdas",
    "Robota riteņi nesaskaras ar grīdu.",
    "Nolieciet robotu uz līdzenas grīdas un spiediet „Turpināt”.",
)
_LOST = (
    "Robots nesaprot, kur atrodas",
    "Robots nevar atrast savu vietu saglabātajā kartē.",
    "Nonesiet robotu uz stacijas un sāciet tīrīšanu no jauna. "
    "Ja tas atkārtojas, skatiet „Karte” → „Ja robots izlaiž vietas”.",
)
_UNREACHABLE = (
    "Robots nav sasniedzams",
    "Ecovacs mākonis nevarēja sazināties ar robotu.",
    "Pārbaudiet, vai robots ir ieslēgts un mājas Wi-Fi darbojas.",
)
_FRESH_WATER = (
    "Tīrā ūdens tvertne ir tukša",
    "Stacijai nav tīra ūdens mopu mazgāšanai.",
    "Piepildiet tīrā ūdens tvertni stacijā un ievietojiet to atpakaļ.",
)
_DIRTY_WATER = (
    "Netīrā ūdens tvertne ir pilna",
    "Stacija nevar savākt vairāk netīrā ūdens.",
    "Izlejiet netīro ūdeni, izskalojiet tvertni un ievietojiet to atpakaļ.",
)
_DUST_BAG = (
    "Jānomaina putekļu maiss",
    "Putekļu maiss stacijā ir pilns.",
    "Atveriet stacijas vāku un ielieciet jaunu putekļu maisu.",
)
_SENSOR = (
    "Sensora kļūme",
    "Viens no robota sensoriem nedarbojas pareizi.",
    "Noslaukiet robota sensorus ar sausu, mīkstu drāniņu un restartējiet robotu.",
)

_TABLE: dict[int, tuple[str, str, str]] = {
    101: (
        "Zems akumulatora līmenis",
        "Robotam gandrīz izlādējies akumulators.",
        "Ļaujiet robotam atgriezties uz stacijas vai novietojiet to tur pats.",
    ),
    102: _OFF_FLOOR,
    402: _OFF_FLOOR,
    103: (
        "Problēma ar riteni",
        "Robota ritenis negriežas pareizi.",
        "Apgrieziet robotu un pārbaudiet, vai riteņos nav ieķērušies mati vai priekšmeti.",
    ),
    104: (
        "Netīri kritiena sensori",
        "Sensori robota apakšā ir netīri, tāpēc robots baidās nokrist.",
        "Noslaukiet sensorus robota apakšā ar sausu drāniņu.",
    ),
    105: _STUCK,
    408: _STUCK,
    106: (
        "Jānomaina sānu birste",
        "Sānu birstes kalpošanas laiks ir beidzies.",
        "Nomainiet sānu birsti. Robots var turpināt tīrīt.",
    ),
    107: (
        "Jānomaina filtrs",
        "Putekļu tvertnes filtra kalpošanas laiks ir beidzies.",
        "Nomainiet filtru. Robots var turpināt tīrīt.",
    ),
    108: (
        "Sapinusies sānu birste",
        "Sānu birstē ir ieķērušies mati vai kāds priekšmets.",
        "Noņemiet sānu birsti, notīriet to un uzlieciet atpakaļ.",
    ),
    109: (
        "Sapinusies galvenā birste",
        "Galvenajā birstē ir ieķērušies mati vai kāds priekšmets.",
        "Izņemiet galveno birsti robota apakšā, notīriet to un ielieciet atpakaļ.",
    ),
    110: (
        "Nav ievietota putekļu tvertne",
        "Robots nevar tīrīt bez putekļu tvertnes.",
        "Ievietojiet putekļu tvertni robotā līdz klikšķim.",
    ),
    111: (
        "Iestrēdzis bamperis",
        "Robota priekšējais bamperis ir iesprūdis.",
        "Viegli paspaidiet bamperi, līdz tas brīvi kustas.",
    ),
    112: (
        "Lāzera sensora kļūme",
        "Robota augšpusē esošais lāzera tornītis nedarbojas.",
        "Pārbaudiet, vai tornītis var brīvi griezties un uz tā nekas nav uzlikts.",
    ),
    113: (
        "Jānomaina galvenā birste",
        "Galvenās birstes kalpošanas laiks ir beidzies.",
        "Nomainiet galveno birsti. Robots var turpināt tīrīt.",
    ),
    114: (
        "Putekļu tvertne ir pilna",
        "Robota putekļu tvertne ir pilna.",
        "Iztukšojiet putekļu tvertni vai ļaujiet stacijai to iztukšot.",
    ),
    118: (
        "Aizsērējis filtrs",
        "Ūdens filtrs ir aizsērējis.",
        "Izņemiet un izskalojiet filtru.",
    ),
    119: (
        "Ventilatora kļūme",
        "Robota sūkšanas ventilators nedarbojas pareizi.",
        "Pārbaudiet putekļu tvertni un filtru. Ja kļūda atkārtojas, sazinieties ar Ecovacs servisu.",
    ),
    121: (
        "Iestrēdzis mops",
        "Mopa plāksne nevar griezties.",
        "Pārbaudiet mopus robota apakšā un noņemiet ieķērušos priekšmetus.",
    ),
    128: (
        "Mopi nav uzlikti",
        "Abi mopi nav pareizi uzlikti.",
        "Uzlieciet abus mopus robota apakšā.",
    ),
    129: (
        "Sapinies mops",
        "Mopā ir ieķēries kāds priekšmets.",
        "Notīriet mopu un uzlieciet to atpakaļ.",
    ),
    208: _SENSOR,
    209: _SENSOR,
    403: _SENSOR,
    301: _FRESH_WATER,
    322: _FRESH_WATER,
    302: _DIRTY_WATER,
    305: _DIRTY_WATER,
    318: _DIRTY_WATER,
    303: (
        "Nav ievietota tīrā ūdens tvertne",
        "Stacijā trūkst tīrā ūdens tvertnes.",
        "Ievietojiet tīrā ūdens tvertni stacijā.",
    ),
    304: (
        "Nav ievietota netīrā ūdens tvertne",
        "Stacijā trūkst netīrā ūdens tvertnes.",
        "Ievietojiet netīrā ūdens tvertni stacijā.",
    ),
    323: (
        "Pārbaudiet netīrā ūdens tvertni",
        "Netīrā ūdens tvertne ir pilna vai nav ievietota.",
        "Izlejiet netīro ūdeni un ievietojiet tvertni atpakaļ stacijā.",
    ),
    306: (
        "Nav ievietots stacijas filtrs",
        "Stacijas mazgāšanas paplātes filtrs nav ievietots.",
        "Ievietojiet filtru stacijas mazgāšanas paplātē.",
    ),
    307: (
        "Stacijas kļūme",
        "Uzlādes un mazgāšanas stacija nedarbojas pareizi.",
        "Atvienojiet staciju no elektrības uz 10 sekundēm un pievienojiet atkal.",
    ),
    310: (
        "Stacijas vāks ir atvērts",
        "Stacija nevar strādāt ar atvērtu vāku.",
        "Aizveriet stacijas vāku.",
    ),
    311: _DUST_BAG,
    312: _DUST_BAG,
    319: (
        "Beidzas tīrīšanas līdzeklis",
        "Stacijā ir maz tīrīšanas līdzekļa.",
        "Papildiniet tīrīšanas līdzekli stacijā.",
    ),
    401: (
        "Robots ir sasvēries",
        "Robots stāv slīpi un nevar droši braukt.",
        "Nolieciet robotu uz līdzenas grīdas.",
    ),
    410: _LOST,
    420: _LOST,
    1062: _LOST,
    1068: _LOST,
    1088: _LOST,
    411: (
        "Robots neatrod staciju",
        "Robots nevar atrast uzlādes staciju.",
        "Pārbaudiet, vai stacija ir pieslēgta elektrībai un tās priekšā nekas neaizsedz ceļu.",
    ),
    1027: (
        "Robots neatrod staciju",
        "Robots nevarēja atrast staciju un brauc uz vietu, kur sāka tīrīt.",
        "Nonesiet robotu uz stacijas pats.",
    ),
    414: (
        "Netīra kamera",
        "Robota priekšējā kamera un sensors ir netīri.",
        "Noslaukiet robota priekšpusi ar sausu, mīkstu drāniņu.",
    ),
    415: (
        "Netīra kamera",
        "Robota kamera ir netīra.",
        "Noslaukiet kameru ar sausu, mīkstu drāniņu.",
    ),
    416: (
        "Akumulators ir pārāk silts",
        "Robota akumulators ir pārkarsis.",
        "Ļaujiet robotam atdzist vēsā vietā un mēģiniet vēlāk.",
    ),
    417: (
        "Akumulators ir pārāk auksts",
        "Robota akumulators ir pārāk auksts.",
        "Novietojiet robotu siltākā telpā un mēģiniet vēlāk.",
    ),
    418: (
        "Robots iebrauca aizliegtā zonā",
        "Robots ir nokļuvis zonā, kur tam nav atļauts braukt.",
        "Nonesiet robotu ārā no aizliegtās zonas un sāciet tīrīšanu no jauna.",
    ),
    500: _UNREACHABLE,
    4200: _UNREACHABLE,
    1024: (
        "Zems akumulators – robots brauc uzlādēties",
        "Robots pārtrauca tīrīšanu, lai uzlādētos.",
        "Nekas nav jādara. Ja ir ieslēgta „Turpināt pēc uzlādes”, robots turpinās pats.",
    ),
    1053: (
        "Tīrīšana pārtraukta",
        "Uzdevums tika pārtraukts, robots brauc uz staciju.",
        "Pārbaudiet robotu un, ja vajag, sāciet tīrīšanu no jauna.",
    ),
    1007: (
        "Aizsērējis mops",
        "Mops ir aizsērējis.",
        "Notīriet vai nomainiet mopus.",
    ),
    2036: (
        "Ceļā ir šķērslis",
        "Robots pamanīja šķērsli.",
        "Novāciet priekšmetu no robota ceļa.",
    ),
}


def translate_error(code: int | None, original: str | None = None) -> ErrorInfo | None:
    """Return a Latvian error for the code, or None if there is no error."""
    if code is None or code in NO_ERROR_CODES:
        return None
    if entry := _TABLE.get(code):
        title, explanation, action = entry
        return ErrorInfo(code, title, explanation, action, original)
    return ErrorInfo(
        code,
        f"Robots ziņo par kļūdu (Nr. {code})",
        "Šai kļūdai mums nav apraksta latviešu valodā.",
        "Apskatiet robotu. Ja problēma nav redzama, atveriet Ecovacs Home lietotni.",
        original,
    )


GENERIC_ERROR = ErrorInfo(
    0,
    "Nepieciešama uzmanība",
    "Robots ziņo par problēmu, bet nepastāstīja, kādu.",
    "Apskatiet robotu. Ja kļūda atkārtojas, lejupielādējiet diagnostiku (Iestatījumi → Diagnostika).",
)


def known_codes() -> frozenset[int]:
    """Codes with a dedicated translation."""
    return frozenset(_TABLE)
