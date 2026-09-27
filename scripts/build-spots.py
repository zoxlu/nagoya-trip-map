#!/usr/bin/env python3
"""
把 Obsidian 景點筆記的 frontmatter 轉成 Deck.gl 可用的 spots.json

用法:
    python3 build-spots.py <筆記資料夾> <輸出檔>

例:
    python3 build-spots.py ./wiki/places ./data/spots.json

設計原則:腳本要能交代它看過的每一個檔案。
收進來的統計、以及「沒收進來的為什麼沒收」,兩邊都要印。
"""

import sys
import json
import re
from collections import Counter
from pathlib import Path

try:
    import yaml
except ImportError:
    print("需要 PyYAML,請先執行:  pip install pyyaml")
    sys.exit(1)


# 會被收進 spots.json 的 type
ACCEPTED_TYPES = ("place", "food", "supermarket")


def read_frontmatter(path):
    """
    讀取檔案最前面 --- 之間的 YAML 區塊。

    回傳 (frontmatter, reason):
        成功 -> (dict, None)
        失敗 -> (None, 'no-frontmatter' | 'yaml-error' | 'not-a-mapping')
    呼叫端要能區分「沒有 frontmatter」與「有但壞掉」,
    否則兩種情況都會變成安靜地少一筆資料。
    """
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return None, "no-frontmatter"
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        print(f"  ⚠️  YAML 解析失敗:{path.name}\n      {e}")
        return None, "yaml-error"
    if not isinstance(data, dict):
        return None, "not-a-mapping"
    return data, None


def parse_location(value):
    """
    '35.05056,136.84333'  (lat,lng)  ->  [136.84333, 35.05056]  (lng,lat)

    注意順序對調:Deck.gl / GeoJSON 規定經度在前。
    """
    if not value or not isinstance(value, str):
        return None
    parts = value.split(",")
    if len(parts) != 2:
        return None
    try:
        lat = float(parts[0].strip())
        lng = float(parts[1].strip())
    except ValueError:
        return None
    # 粗略合理性檢查,抓出寫反的資料
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        print(f"  ⚠️  座標超出範圍,可能 lat/lng 寫反了:{value}")
        return None
    return [lng, lat]


def first_or_none(value):
    """place_category 這類欄位有時是 list、有時是字串,統一取第一個。"""
    if isinstance(value, list):
        return value[0] if value else None
    return value


def normalize_days(value):
    """
    day_assigned 可能是 None、'Day1'、或 [Day1, Day6]。
    統一成字串陣列,沒排的回傳空陣列。
    """
    if value is None or value == "":
        return []
    if not isinstance(value, list):
        value = [value]
    return [str(v).strip() for v in value if v is not None and str(v).strip()]


def build_spot(fm):
    """把一份 frontmatter 轉成一筆 spot。缺座標就回傳 None。"""
    position = parse_location(fm.get("location"))
    if position is None:
        return None

    # food 筆記用 food_category,place 筆記用 place_category
    category = first_or_none(fm.get("place_category")) or first_or_none(fm.get("food_category"))

    spot = {
        "name": fm.get("map_label") or fm.get("title") or "(未命名)",
        "title": fm.get("title"),
        "position": position,
        "type": fm.get("type"),          # place / food / supermarket
        # 中文鍵轉英文,讓資料進入程式後統一用英文
        "interest": fm.get("興致指數"),
        "category": category,
        "district": fm.get("district"),
        "station": fm.get("station"),
        "lines": fm.get("lines") or [],
        "duration": fm.get("duration"),
        "status": fm.get("status"),
        "priority": fm.get("priority"),
        # food 專屬欄位
        "meal_slot": fm.get("meal_slot"),
        "cuisine": fm.get("cuisine"),
        "price_range": fm.get("price_range"),
        "booking_required": fm.get("booking_required"),
        "image": fm.get("image"),
        "official_url": fm.get("official_url"),
        # day_assigned 可能是 None / 單值 / 陣列,統一成陣列
        "days": normalize_days(fm.get("day_assigned")),
    }

    # 附近廁所:保留座標,之後可做成獨立圖層
    restrooms = []
    for r in (fm.get("nearby_restrooms") or []):
        pos = parse_location(r.get("location"))
        if pos:
            restrooms.append({
                "name": r.get("name"),
                "position": pos,
                "distance": r.get("distance"),
            })
    if restrooms:
        spot["restrooms"] = restrooms

    # 拿掉值為 None 的欄位,讓 JSON 乾淨一點
    return {k: v for k, v in spot.items() if v is not None}


def report(spots, scanned, excluded, seen_types):
    """把「收了什麼」與「沒收什麼」一起印出來,並確認兩邊加起來等於掃到的檔案數。"""
    print("\n📊 掃描結果")
    print(f"   掃到 .md    : {scanned} 個檔案")
    print(f"   寫入        : {len(spots)} 筆")

    total_excluded = sum(len(v) for v in excluded.values())
    print(f"   未收        : {total_excluded} 筆")
    for reason, names in excluded.items():
        if not names:
            continue
        print(f"     - {reason:<22}: {len(names)} 筆")
        for name in names[:10]:
            print(f"         · {name}")
        if len(names) > 10:
            print(f"         · ...還有 {len(names) - 10} 筆")

    # 對帳:任何一筆資料都必須有去處,對不起來就是有路徑沒被計數
    if len(spots) + total_excluded != scanned:
        print(f"\n   ❗ 對帳不符:{len(spots)} + {total_excluded} ≠ {scanned}")

    # 包含「不收的 type」,新增 type 時才不會安靜消失
    print("\n   掃到的 type(含未收):", dict(seen_types))
    unknown = {t: n for t, n in seen_types.items() if t not in ACCEPTED_TYPES}
    if unknown:
        print(f"   ⚠️  有 {sum(unknown.values())} 筆的 type 不在收取清單內:{dict(unknown)}")
        print("       如果這是新的分類,要更新 ACCEPTED_TYPES。")

    if not spots:
        return

    print("\n📊 已收資料")
    print("   type     :", dict(Counter(s.get("type") for s in spots)))
    print("   category :", dict(Counter(s.get("category") for s in spots)))

    day_counter = Counter()
    unassigned = 0
    for s in spots:
        ds = s.get("days") or []
        if not ds:
            unassigned += 1
        for d in ds:
            day_counter[d] += 1
    print("   days     :", dict(sorted(day_counter.items())))
    print(f"   未排行程 : {unassigned} 筆")

    missing_interest = [s["name"] for s in spots if "interest" not in s]
    if missing_interest:
        print(f"\n📋 沒有興致指數({len(missing_interest)} 筆):")
        for name in missing_interest[:10]:
            print(f"   - {name}")
        if len(missing_interest) > 10:
            print(f"   ...還有 {len(missing_interest) - 10} 筆")


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    src_dir = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    if not src_dir.is_dir():
        print(f"找不到資料夾:{src_dir}")
        sys.exit(1)

    spots = []
    scanned = 0
    seen_types = Counter()
    # 每一種「沒收」的理由都要留檔名,否則就是安靜地少資料
    excluded = {
        "no-frontmatter": [],
        "yaml-error": [],
        "not-a-mapping": [],
        "type-not-collected": [],
        "no-valid-location": [],
    }

    # rglob 會連子資料夾一起掃
    for md_path in sorted(src_dir.rglob("*.md")):
        scanned += 1

        fm, reason = read_frontmatter(md_path)
        if fm is None:
            excluded[reason].append(md_path.name)
            continue

        spot_type = fm.get("type")
        seen_types[spot_type if spot_type is not None else "(no type)"] += 1
        if spot_type not in ACCEPTED_TYPES:
            excluded["type-not-collected"].append(md_path.name)
            continue

        spot = build_spot(fm)
        if spot is None:
            excluded["no-valid-location"].append(md_path.name)
            continue

        spots.append(spot)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(spots, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"✅ 寫出 {len(spots)} 筆 → {out_path}")
    report(spots, scanned, excluded, seen_types)


if __name__ == "__main__":
    main()
