import urllib.request
import gzip
import sqlite3
import ipaddress
import time
import os
import re

start_time = time.time()
print("Starting database generation...")

COUNTRIES = {
    'UA': {'name_en': 'Ukraine', 'name_ru': 'Украина', 'region': 'Ukraine'},
    'US': {'name_en': 'United States', 'name_ru': 'США', 'region': 'United States'},
    'AL': {'name_en': 'Albania', 'name_ru': 'Албания', 'region': 'Europe'},
    'AD': {'name_en': 'Andorra', 'name_ru': 'Андорра', 'region': 'Europe'},
    'AT': {'name_en': 'Austria', 'name_ru': 'Австрия', 'region': 'Europe'},
    'AX': {'name_en': 'Aland Islands', 'name_ru': 'Аландские острова', 'region': 'Europe'},
    'BA': {'name_en': 'Bosnia and Herzegovina', 'name_ru': 'Босния и Герцеговина', 'region': 'Europe'},
    'BE': {'name_en': 'Belgium', 'name_ru': 'Бельгия', 'region': 'Europe'},
    'BG': {'name_en': 'Bulgaria', 'name_ru': 'Болгария', 'region': 'Europe'},
    'BY': {'name_en': 'Belarus', 'name_ru': 'Беларусь', 'region': 'Europe'},
    'CH': {'name_en': 'Switzerland', 'name_ru': 'Швейцария', 'region': 'Europe'},
    'CY': {'name_en': 'Cyprus', 'name_ru': 'Кипр', 'region': 'Europe'},
    'CZ': {'name_en': 'Czech Republic', 'name_ru': 'Чехия', 'region': 'Europe'},
    'DE': {'name_en': 'Germany', 'name_ru': 'Германия', 'region': 'Europe'},
    'DK': {'name_en': 'Denmark', 'name_ru': 'Дания', 'region': 'Europe'},
    'EE': {'name_en': 'Estonia', 'name_ru': 'Эстония', 'region': 'Europe'},
    'ES': {'name_en': 'Spain', 'name_ru': 'Испания', 'region': 'Europe'},
    'FI': {'name_en': 'Finland', 'name_ru': 'Финляндия', 'region': 'Europe'},
    'FO': {'name_en': 'Faroe Islands', 'name_ru': 'Фарерские острова', 'region': 'Europe'},
    'FR': {'name_en': 'France', 'name_ru': 'Франция', 'region': 'Europe'},
    'GB': {'name_en': 'United Kingdom', 'name_ru': 'Великобритания', 'region': 'Europe'},
    'GG': {'name_en': 'Guernsey', 'name_ru': 'Гернси', 'region': 'Europe'},
    'GI': {'name_en': 'Gibraltar', 'name_ru': 'Гибралтар', 'region': 'Europe'},
    'GR': {'name_en': 'Greece', 'name_ru': 'Греция', 'region': 'Europe'},
    'HR': {'name_en': 'Croatia', 'name_ru': 'Хорватия', 'region': 'Europe'},
    'HU': {'name_en': 'Hungary', 'name_ru': 'Венгрия', 'region': 'Europe'},
    'IE': {'name_en': 'Ireland', 'name_ru': 'Ирландия', 'region': 'Europe'},
    'IM': {'name_en': 'Isle of Man', 'name_ru': 'Остров Мэн', 'region': 'Europe'},
    'IS': {'name_en': 'Iceland', 'name_ru': 'Исландия', 'region': 'Europe'},
    'IT': {'name_en': 'Italy', 'name_ru': 'Италия', 'region': 'Europe'},
    'JE': {'name_en': 'Jersey', 'name_ru': 'Джерси', 'region': 'Europe'},
    'LI': {'name_en': 'Liechtenstein', 'name_ru': 'Лихтенштейн', 'region': 'Europe'},
    'LT': {'name_en': 'Lithuania', 'name_ru': 'Литва', 'region': 'Europe'},
    'LU': {'name_en': 'Luxembourg', 'name_ru': 'Люксембург', 'region': 'Europe'},
    'LV': {'name_en': 'Latvia', 'name_ru': 'Латвия', 'region': 'Europe'},
    'MC': {'name_en': 'Monaco', 'name_ru': 'Монако', 'region': 'Europe'},
    'MD': {'name_en': 'Moldova', 'name_ru': 'Молдова', 'region': 'Europe'},
    'ME': {'name_en': 'Montenegro', 'name_ru': 'Черногория', 'region': 'Europe'},
    'MK': {'name_en': 'North Macedonia', 'name_ru': 'Северная Македония', 'region': 'Europe'},
    'MT': {'name_en': 'Malta', 'name_ru': 'Мальта', 'region': 'Europe'},
    'NL': {'name_en': 'Netherlands', 'name_ru': 'Нидерланды', 'region': 'Europe'},
    'NO': {'name_en': 'Norway', 'name_ru': 'Норвегия', 'region': 'Europe'},
    'PL': {'name_en': 'Poland', 'name_ru': 'Польша', 'region': 'Europe'},
    'PT': {'name_en': 'Portugal', 'name_ru': 'Португалия', 'region': 'Europe'},
    'RO': {'name_en': 'Romania', 'name_ru': 'Румыния', 'region': 'Europe'},
    'RS': {'name_en': 'Serbia', 'name_ru': 'Сербия', 'region': 'Europe'},
    'SE': {'name_en': 'Sweden', 'name_ru': 'Швеция', 'region': 'Europe'},
    'SI': {'name_en': 'Slovenia', 'name_ru': 'Словения', 'region': 'Europe'},
    'SK': {'name_en': 'Slovakia', 'name_ru': 'Словакия', 'region': 'Europe'},
    'SM': {'name_en': 'San Marino', 'name_ru': 'Сан-Марино', 'region': 'Europe'},
    'SJ': {'name_en': 'Svalbard and Jan Mayen', 'name_ru': 'Шпицберген и Ян-Майен', 'region': 'Europe'},
    'VA': {'name_en': 'Vatican City', 'name_ru': 'Ватикан', 'region': 'Europe'},
    'XK': {'name_en': 'Kosovo', 'name_ru': 'Косово', 'region': 'Europe'},
}

print("Fetching RIPE ASN database...")
asn_names = {}
try:
    req = urllib.request.Request('https://ftp.ripe.net/ripe/asnames/asn.txt', headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        for line in resp.read().decode('utf-8', errors='ignore').splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(' ', 1)
            if len(parts) == 2 and parts[0].isdigit():
                asn_num = int(parts[0])
                rest = parts[1].strip()
                m = re.match(r'^(.*?)(?:,\s*([A-Z]{2}))?$', rest)
                if m:
                    asn_names[asn_num] = {
                        'full': m.group(1).strip(),
                        'cc': m.group(2) or ''
                    }
    print(f"Loaded {len(asn_names)} ASN directory records.")
except Exception as e:
    print(f"Warning downloading ASN directory: {e}")

tsv_path = '/tmp/ip2asn.tsv.gz'
if not os.path.exists(tsv_path):
    print("Downloading ip2asn combined dataset...")
    req = urllib.request.Request('https://iptoasn.com/data/ip2asn-combined.tsv.gz', headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp, open(tsv_path, 'wb') as out:
        out.write(resp.read())

db_dest = '/home/user/isp_cidr.db'
if os.path.exists(db_dest):
    os.remove(db_dest)

conn = sqlite3.connect(db_dest)
cur = conn.cursor()

cur.execute("PRAGMA page_size = 4096;")
cur.execute("PRAGMA synchronous = OFF;")
cur.execute("PRAGMA journal_mode = MEMORY;")
cur.execute("PRAGMA cache_size = 100000;")

cur.execute("""
CREATE TABLE countries (
    country_code TEXT PRIMARY KEY,
    country_name_en TEXT NOT NULL,
    country_name_ru TEXT NOT NULL,
    region TEXT NOT NULL,
    total_asns INTEGER DEFAULT 0,
    total_v4_cidrs INTEGER DEFAULT 0,
    total_v6_cidrs INTEGER DEFAULT 0,
    total_cidrs INTEGER DEFAULT 0,
    total_ipv4_ips INTEGER DEFAULT 0
);
""")

cur.execute("""
CREATE TABLE providers (
    asn INTEGER PRIMARY KEY,
    as_name TEXT,
    org_name TEXT NOT NULL,
    country_code TEXT NOT NULL,
    country_name_en TEXT NOT NULL,
    country_name_ru TEXT NOT NULL,
    region TEXT NOT NULL,
    ipv4_cidr_count INTEGER DEFAULT 0,
    ipv6_cidr_count INTEGER DEFAULT 0,
    total_ipv4_ips INTEGER DEFAULT 0
);
""")

cur.execute("""
CREATE TABLE cidr_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cidr TEXT NOT NULL,
    ip_version INTEGER NOT NULL,
    asn INTEGER,
    country_code TEXT NOT NULL,
    total_ips INTEGER
);
""")

cur.execute("""
CREATE TABLE ip_ranges (
    cidr_id INTEGER PRIMARY KEY REFERENCES cidr_blocks(id),
    start_ip TEXT NOT NULL,
    end_ip TEXT NOT NULL,
    start_ip_int INTEGER,
    end_ip_int INTEGER,
    netmask TEXT,
    wildcard_mask TEXT
);
""")

print("Parsing IP blocks and calculating CIDR subnets & ranges...")
provider_stats = {}
batch_cidr = []
batch_ranges = []
total_cidrs = 0

with gzip.open(tsv_path, 'rt', encoding='utf-8', errors='ignore') as f:
    for line in f:
        parts = line.strip().split('\t')
        if len(parts) < 5:
            continue
        start_ip_str, end_ip_str, asn_str, cc, org_desc = parts[0], parts[1], parts[2], parts[3].upper(), parts[4]
        if cc not in COUNTRIES:
            continue
        
        try:
            asn = int(asn_str)
        except ValueError:
            asn = 0
            
        c_info = COUNTRIES[cc]
        region = c_info['region']
        c_en = c_info['name_en']
        c_ru = c_info['name_ru']
        
        isp_name = org_desc
        if asn in asn_names and asn_names[asn]['full']:
            ripe_name = asn_names[asn]['full']
            if len(ripe_name) > len(org_desc) or org_desc.startswith('AS'):
                isp_name = ripe_name
        
        try:
            s_ip = ipaddress.ip_address(start_ip_str)
            e_ip = ipaddress.ip_address(end_ip_str)
            subnets = list(ipaddress.summarize_address_range(s_ip, e_ip))
        except Exception:
            continue
            
        if asn not in provider_stats and asn > 0:
            provider_stats[asn] = {
                'asn': asn,
                'name': isp_name,
                'cc': cc,
                'c_en': c_en,
                'c_ru': c_ru,
                'region': region,
                'v4_cidrs': 0,
                'v6_cidrs': 0,
                'v4_ips': 0
            }
            
        p_stat = provider_stats.get(asn)
        
        for net in subnets:
            total_cidrs += 1
            c_id = total_cidrs
            cidr_str = str(net)
            v = net.version
            n_addrs = net.num_addresses
            s_int = int(net.network_address) if v == 4 else None
            e_int = int(net.broadcast_address) if v == 4 else None
            s_str = str(net.network_address)
            e_str = str(net.broadcast_address)
            
            netmask = None
            wildcard = None
            if v == 4:
                prefix_len = int(cidr_str.split('/')[1])
                mask_int = (0xFFFFFFFF << (32 - prefix_len)) & 0xFFFFFFFF
                wildcard_int = ~mask_int & 0xFFFFFFFF
                netmask = str(ipaddress.IPv4Address(mask_int))
                wildcard = str(ipaddress.IPv4Address(wildcard_int))
            else:
                netmask = '/' + cidr_str.split('/')[1]

            if p_stat:
                if v == 4:
                    p_stat['v4_cidrs'] += 1
                    p_stat['v4_ips'] += n_addrs
                else:
                    p_stat['v6_cidrs'] += 1
                    
            batch_cidr.append((c_id, cidr_str, v, asn if asn > 0 else None, cc, n_addrs if v == 4 else None))
            batch_ranges.append((c_id, s_str, e_str, s_int, e_int, netmask, wildcard))
            
            if len(batch_cidr) >= 50000:
                cur.executemany("INSERT INTO cidr_blocks VALUES (?, ?, ?, ?, ?, ?)", batch_cidr)
                cur.executemany("INSERT INTO ip_ranges VALUES (?, ?, ?, ?, ?, ?, ?)", batch_ranges)
                conn.commit()
                batch_cidr.clear()
                batch_ranges.clear()

if batch_cidr:
    cur.executemany("INSERT INTO cidr_blocks VALUES (?, ?, ?, ?, ?, ?)", batch_cidr)
    cur.executemany("INSERT INTO ip_ranges VALUES (?, ?, ?, ?, ?, ?, ?)", batch_ranges)
    conn.commit()
    batch_cidr.clear()
    batch_ranges.clear()

print(f"Total CIDRs and Ranges inserted: {total_cidrs}")

# Providers
prov_batch = []
for asn, info in provider_stats.items():
    full_n = info['name']
    as_handle = full_n.split(' ')[0] if ' ' in full_n else full_n
    prov_batch.append((
        asn,
        as_handle,
        full_n,
        info['cc'],
        info['c_en'],
        info['c_ru'],
        info['region'],
        info['v4_cidrs'],
        info['v6_cidrs'],
        info['v4_ips']
    ))

cur.executemany("""
INSERT INTO providers (
    asn, as_name, org_name, country_code,
    country_name_en, country_name_ru, region,
    ipv4_cidr_count, ipv6_cidr_count, total_ipv4_ips
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", prov_batch)
conn.commit()

# Countries
cur.execute("""
INSERT INTO countries (
    country_code, country_name_en, country_name_ru, region,
    total_asns, total_v4_cidrs, total_v6_cidrs, total_cidrs, total_ipv4_ips
)
SELECT 
    c.country_code,
    MAX(p.country_name_en),
    MAX(p.country_name_ru),
    MAX(p.region),
    COUNT(DISTINCT c.asn),
    SUM(CASE WHEN c.ip_version = 4 THEN 1 ELSE 0 END),
    SUM(CASE WHEN c.ip_version = 6 THEN 1 ELSE 0 END),
    COUNT(*),
    SUM(COALESCE(c.total_ips, 0))
FROM cidr_blocks c
LEFT JOIN providers p ON c.asn = p.asn
GROUP BY c.country_code;
""")

for cc, c_info in COUNTRIES.items():
    cur.execute("""
    UPDATE countries 
    SET country_name_en = ?, country_name_ru = ?, region = ?
    WHERE country_code = ? AND (country_name_en IS NULL OR country_name_ru IS NULL)
    """, (c_info['name_en'], c_info['name_ru'], c_info['region'], cc))

# Views
cur.execute("""
CREATE VIEW v_cidr_details AS
SELECT 
    c.id,
    c.cidr,
    c.ip_version,
    c.asn,
    COALESCE(p.org_name, 'Unknown Provider') AS isp_name,
    c.country_code,
    cnt.country_name_en,
    cnt.country_name_ru,
    cnt.region,
    r.start_ip,
    r.end_ip,
    r.start_ip_int,
    r.end_ip_int,
    r.netmask,
    r.wildcard_mask,
    c.total_ips AS ip_count
FROM cidr_blocks c
LEFT JOIN ip_ranges r ON c.id = r.cidr_id
LEFT JOIN providers p ON c.asn = p.asn
LEFT JOIN countries cnt ON c.country_code = cnt.country_code;
""")

cur.execute("""
CREATE VIEW v_ip_ranges AS
SELECT 
    r.cidr_id,
    c.cidr,
    c.ip_version,
    r.start_ip,
    r.end_ip,
    r.start_ip_int,
    r.end_ip_int,
    r.netmask,
    r.wildcard_mask,
    c.total_ips,
    c.asn,
    COALESCE(p.org_name, 'Unknown Provider') AS isp_name,
    c.country_code,
    cnt.country_name_en,
    cnt.country_name_ru,
    cnt.region
FROM ip_ranges r
JOIN cidr_blocks c ON r.cidr_id = c.id
LEFT JOIN providers p ON c.asn = p.asn
LEFT JOIN countries cnt ON c.country_code = cnt.country_code;
""")

# Indexes
print("Creating database indexes...")
cur.execute("CREATE INDEX idx_cidr_cidr ON cidr_blocks(cidr);")
cur.execute("CREATE INDEX idx_cidr_asn ON cidr_blocks(asn);")
cur.execute("CREATE INDEX idx_cidr_cc ON cidr_blocks(country_code);")
cur.execute("CREATE INDEX idx_range_range ON ip_ranges(start_ip_int, end_ip_int);")
cur.execute("CREATE INDEX idx_prov_org ON providers(org_name);")
cur.execute("CREATE INDEX idx_prov_cc ON providers(country_code);")

conn.commit()
conn.execute("VACUUM;")
conn.close()

db_size_mb = os.path.getsize(db_dest) / (1024 * 1024)
print(f"Database generated successfully in {time.time() - start_time:.2f}s! DB size: {db_size_mb:.2f} MB")
