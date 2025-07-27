import json
import os
from collections import OrderedDict

def load_json(file_path):
    """Load JSON data from a file."""
    if not os.path.exists(file_path):
        print(f"File {file_path} not found.")
        return []
    with open(file_path, 'r') as f:
        return json.load(f)

def normalize_os(os_value):
    """Normalize OS formatting for consistency."""
    if not os_value or os_value == "N/A":
        return "N/A"
    os_lower = os_value.lower()
    if "windows" in os_lower:
        # Remove extra characters and standardize to "Windows 11"
        os_cleaned = "Windows 11" if "11" in os_lower else "Windows"
        return os_cleaned
    return os_value

def categorize_laptop(specs):
    """Categorize the laptop based on its specs."""
    weight = specs.get("weight", "N/A")
    gpu = specs.get("gpu", "N/A").lower()
    resolution = specs.get("resolution", "N/A").lower()

    # Convert weight to float for comparison
    try:
        weight_value = float(weight.split()[0]) if weight != "N/A" else float("inf")
    except (ValueError, IndexError):
        weight_value = float("inf")

    # Gaming: Has a dedicated GPU (NVIDIA/AMD)
    if any(g in gpu for g in ["nvidia", "geforce", "rtx", "radeon"]):
        return "Gaming"
    
    # Ultraportable: Lightweight (under 1.5 kg)
    if weight_value != float("inf") and weight_value <= 1.5:
        return "Ultraportable"
    
    # Creator: High-resolution display (OLED, WUXGA, QHD, 2K, 4K)
    if any(g in resolution for g in ["oled", "wuxga", "qhd", "2k", "4k"]):
        return "Creator"
    
    # Default: Productivity
    return "Productivity"

def compute_score(product):
    """Compute a weighted score based on price and rating."""
    try:
        # Extract price (remove ₹ and commas)
        price = float(product["price"].replace("₹", "").replace(",", ""))
    except (ValueError, AttributeError):
        price = float("inf")  # High price if unparseable

    # Parse rating
    try:
        rating_str = product["rating"]
        if "out of" in rating_str:
            rating = float(rating_str.split()[0])
        else:
            rating = float(rating_str)
    except (ValueError, AttributeError):
        rating = 0  # Default to 0 if rating is missing or unparseable

    # Weighted score: Lower price and higher rating are better
    # Normalize price (lower is better) and rating (higher is better)
    # Score = rating * 5 - (price / 10000)
    if price == float("inf"):
        score = rating * 5  # If price is unparseable, rely on rating
    else:
        score = (rating * 5) - (price / 10000)  # Rating has more weight
    return score

def deduplicate_products(products):
    """Deduplicate products based on name similarity."""
    seen = set()
    deduplicated = []
    for product in products:
        # Simplify name for deduplication (remove model numbers and extra details)
        name = product["name"].lower()
        name_key = " ".join(name.split()[:5])  # First 5 words for deduplication
        if name_key not in seen:
            seen.add(name_key)
            deduplicated.append(product)
    return deduplicated

def combine_and_recommend(flipkart_file, amazon_file, top_n=5):
    """Combine products from Flipkart and Amazon, categorize, and recommend."""
    # Load data
    flipkart_products = load_json(flipkart_file)
    amazon_products = load_json(amazon_file)

    # Combine all products
    all_products = flipkart_products + amazon_products

    # Deduplicate products
    deduplicated_products = deduplicate_products(all_products)
    print(f"Total deduplicated products: {len(deduplicated_products)}")

    # Categorize and normalize specs
    categorized_products = []
    for product in deduplicated_products:
        specs = product["specifications"]
        # Normalize OS
        specs["os"] = normalize_os(specs.get("os", "N/A"))
        # Categorize
        category = categorize_laptop(specs)
        # Compute score
        score = compute_score(product)
        categorized_products.append((product, category, score))

    # Sort by score (higher is better)
    categorized_products.sort(key=lambda x: x[2], reverse=True)

    # Select top N products, ensuring diversity in categories
    selected_products = []
    seen_categories = set()
    for product, category, score in categorized_products:
        if len(selected_products) >= top_n:
            break
        # Add at least one product from each category if possible
        if category not in seen_categories or len(selected_products) >= len(set(c[1] for c in categorized_products)):
            selected_products.append((product, category))
            seen_categories.add(category)

    # If we don't have enough products, fill with highest-scored remaining
    remaining = [(p, c) for p, c, s in sorted(categorized_products, key=lambda x: x[2], reverse=True) if (p, c) not in selected_products]
    selected_products.extend(remaining[:top_n - len(selected_products)])

    # Print recommendations
    print("\nRecommended Laptops:")
    recommended_list = []
    for i, (product, category) in enumerate(selected_products, 1):
        specs = product["specifications"]
        specs_str = f"{specs['processor']}, {specs['ram']}, {specs['ssd']}, {specs['display_size']}, {specs['resolution']}, {specs['weight']}, {specs['gpu']}, {specs['os']}"
        print(f"{i}. {product['name']} ({product['site']}): {product['price']}")
        print(f"   Category: {category}")
        print(f"   Specs: {specs_str}")
        print(f"   Link: {product['link']}\n")
        recommended_list.append([product, category])

    # Save recommendations to JSON file
    os.makedirs("data", exist_ok=True)
    output_file = "data/recommended_laptops.json"
    with open(output_file, "w") as f:
        json.dump(recommended_list, f, indent=2)
    print(f"Recommendations saved to {output_file}")

    return recommended_list

if __name__ == "__main__":
    flipkart_file = "data/flipkart_results.json"
    amazon_file = "data/amazon_results.json"
    recommended = combine_and_recommend(flipkart_file, amazon_file, top_n=10)