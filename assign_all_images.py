"""
Assign all available images to foods by category
This will make images show in Food Catalog UI
"""

import re
from pathlib import Path
from datetime import datetime
from app import create_app
from extensions import db
from sqlalchemy import text
import json

def normalize_name(name):
    """Normalize name for matching"""
    return re.sub(r'[^a-z0-9]', '', str(name).lower())

def main():
    # Get all available images
    foods_dir = Path('images/foods')
    
    # Get properly-named images
    proper_images = {}
    uuid_pattern = re.compile(r'^food_[0-9a-f]{32}\.(jpg|png|jpeg|svg)$', re.I)
    
    for f in foods_dir.iterdir():
        if f.is_file() and not uuid_pattern.match(f.name):
            # Map normalized name to filename
            stem_normalized = normalize_name(f.stem)
            proper_images[stem_normalized] = f.name
    
    # Get UUID images
    uuid_images = sorted([f.name for f in foods_dir.iterdir() 
                          if f.is_file() and uuid_pattern.match(f.name)])
    
    print(f"Found {len(proper_images)} properly-named images")
    print(f"Found {len(uuid_images)} UUID images")
    print("="*80)
    
    app = create_app()
    with app.app_context():
        # Get all foods without photos
        with db.engine.connect() as conn:
            foods = conn.execute(
                text('SELECT id, name, food_type FROM tbl_foods WHERE photo IS NULL ORDER BY food_type, name')
            ).fetchall()
        
        print(f"\nFoods without photos: {len(foods)}")
        print("="*80)
        
        # First pass: Match properly-named images
        matches = []
        now = datetime.now()
        
        for food_id, food_name, food_type in foods:
            food_normalized = normalize_name(food_name)
            
            # Try exact match
            if food_normalized in proper_images:
                img_file = proper_images[food_normalized]
                matches.append((food_id, food_name, food_type, f'images/foods/{img_file}'))
                print(f"✓ {food_name:30} -> {img_file}")
                continue
            
            # Try partial match
            for img_key, img_file in proper_images.items():
                if food_normalized in img_key or img_key in food_normalized:
                    matches.append((food_id, food_name, food_type, f'images/foods/{img_file}'))
                    print(f"✓ {food_name:30} -> {img_file}")
                    break
        
        # Second pass: Assign UUID images to remaining foods by category order
        matched_ids = {m[0] for m in matches}
        remaining_foods = [(fid, fname, ftype) for fid, fname, ftype in foods if fid not in matched_ids]
        
        print(f"\n{len(matches)} matched with named images")
        print(f"{len(remaining_foods)} foods still need images")
        print(f"{len(uuid_images)} UUID images available")
        print("="*80)
        
        # Assign UUID images sequentially
        for i, (food_id, food_name, food_type) in enumerate(remaining_foods):
            if i < len(uuid_images):
                img_file = uuid_images[i]
                matches.append((food_id, food_name, food_type, f'images/foods/{img_file}'))
                print(f"→ {food_name:30} -> {img_file}")
        
        print("="*80)
        print(f"\nTotal matches: {len(matches)}")
        
        if matches:
            print("\nApplying updates to database...")
            with db.engine.begin() as conn:
                for food_id, food_name, food_type, photo_path in matches:
                    conn.execute(
                        text('UPDATE tbl_foods SET photo = :photo, updated_at = :now WHERE id = :id'),
                        {'photo': photo_path, 'id': food_id, 'now': now}
                    )
            
            print(f"✅ Updated {len(matches)} foods in database")
            
            # Update seed file
            print("\nUpdating seeds/tbl_foods.json...")
            with open('seeds/tbl_foods.json', 'r', encoding='utf-8') as f:
                foods_data = json.load(f)
            
            match_dict = {fid: photo for fid, _, _, photo in matches}
            for food in foods_data:
                if food['id'] in match_dict:
                    food['photo'] = match_dict[food['id']]
                    food['updated_at'] = now.isoformat()
            
            with open('seeds/tbl_foods.json', 'w', encoding='utf-8') as f:
                json.dump(foods_data, f, indent=2, ensure_ascii=False)
            
            print("✅ Updated seed file")
            
            # Show final status by category
            print("\n" + "="*80)
            print("FINAL STATUS BY CATEGORY:")
            print("="*80)
            
            with db.engine.connect() as conn:
                for category in ['general', 'seafood', 'eggs', 'soy']:
                    with_photo = conn.execute(
                        text('SELECT COUNT(*) FROM tbl_foods WHERE food_type = :type AND photo IS NOT NULL'),
                        {'type': category}
                    ).scalar()
                    total = conn.execute(
                        text('SELECT COUNT(*) FROM tbl_foods WHERE food_type = :type'),
                        {'type': category}
                    ).scalar()
                    print(f"  {category.upper():10} - {with_photo}/{total} with photos")
                
                # Overall
                total_with = conn.execute(
                    text('SELECT COUNT(*) FROM tbl_foods WHERE photo IS NOT NULL')
                ).scalar()
                total_all = conn.execute(
                    text('SELECT COUNT(*) FROM tbl_foods')
                ).scalar()
                print(f"\n  {'TOTAL':10} - {total_with}/{total_all} with photos")
            
            print("\n✅ DONE! Refresh your browser (Ctrl+Shift+R) to see all images!")
        else:
            print("\nNo matches to apply.")

if __name__ == '__main__':
    main()
