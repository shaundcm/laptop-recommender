from playwright.sync_api import sync_playwright
import re
import random
import time
import json
import os

# List of user agents to rotate
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
]

def extract_specs_from_name(name, link=""):
    """Extract specifications from the product name with enhanced parsing, using the link for additional context."""
    specs = {
        "processor": "N/A",
        "ram": "N/A",
        "ssd": "N/A",
        "display_size": "N/A",
        "gpu": "N/A",
        "os": "N/A",
        "weight": "N/A",
        "battery": "N/A",
        "refresh_rate": "N/A",
        "resolution": "N/A"
    }

    name_lower = name.lower()
    link_lower = link.lower()

    # Extract processor (ensure full model number is captured)
    processor_match = re.search(r"(intel\s*core\s*(i[3-9]|ultra\s*[5-7])(?:\s*\d{1,2}(?:th)?\s*gen)?|amd\s*ryzen\s*[3-9](?:\s*\d{1,2}(?:th)?\s*gen)?|snapdragon|apple\s*m[1-3])(?:\s*[\w-]*(?:\d{4,5}[u|h]?[a-z]{1,2}))?", name_lower, re.IGNORECASE)
    if processor_match:
        processor = processor_match.group(0).strip()
        if processor.endswith("-"):
            processor = processor[:-1].strip()
        specs["processor"] = processor

    # Extract RAM
    ram_match = re.search(r"(\d{1,2})\s*gb\s*(?:ram|lpddr|ddr|\(ram\)|memory)?(?:[/\s-]|$)", name_lower, re.IGNORECASE)
    if ram_match:
        specs["ram"] = ram_match.group(1) + "GB"

    # Extract SSD
    ssd_match = re.search(r"(?:(?:/|\s))(\d{1,4})\s*(gb|tb)\s*(?:ssd|hdd|storage)?(?:[/\s]|$)", name_lower, re.IGNORECASE)
    if ssd_match:
        size = ssd_match.group(1)
        unit = ssd_match.group(2).upper()
        specs["ssd"] = f"{size}{unit}"

    # Extract display size (more robust, handle numbers in model names)
    display_match = re.search(r"(\d{1,2}(?:\.\d)?)\s*(?:inch|cm|['\"]|[-]inch)(?:\s*(?:display|screen|fhd|wuxga|qhd))?", name_lower, re.IGNORECASE)
    if display_match:
        size = float(display_match.group(1))
        unit = display_match.group(0).lower()
        if "cm" in unit:
            size = round(size / 2.54, 1)  # Convert cm to inches
        specs["display_size"] = f"{size} inch"
    else:
        # Fallback: Look for numbers in common display size range (e.g., 12-17) in model name
        display_fallback = re.search(r"(?<!\d{4})(\d{1,2}(?:\.\d)?)(?=\s*(?:g\d+|evo|plus|pro|thin|light|laptop|modern|firefly|victus|inspiron|inbook|pavilion|\.\.\.|\s|$))", name_lower)
        if display_fallback:
            size = float(display_fallback.group(1))
            if 12 <= size <= 17:  # Common laptop display sizes
                specs["display_size"] = f"{size} inch"
        else:
            # Fallback 2: Extract display size from the link (e.g., "15-fa1389tx", "14-eh0024tu")
            link_display_match = re.search(r"(?:\/|-)(\d{1,2}(?:\.\d)?)(?:-fa|-eh|-nbc|-inbook|-inspiron)", link_lower)
            if link_display_match:
                size = float(link_display_match.group(1))
                if 12 <= size <= 17:
                    specs["display_size"] = f"{size} inch"

    # Extract GPU (prioritize specific GPUs over generic "X GB Graphics")
    specific_gpu_match = re.search(r"(nvidia\s*geforce|rtx|amd\s*radeon|iris\s*xe|adreno)\s*(?:\d{3,4})?", name_lower, re.IGNORECASE)
    if specific_gpu_match:
        specs["gpu"] = specific_gpu_match.group(0).strip()
    else:
        generic_gpu_match = re.search(r"(\d\s*gb\s*graphics)", name_lower, re.IGNORECASE)
        if generic_gpu_match:
            specs["gpu"] = generic_gpu_match.group(1).strip()
        elif "integrated" in name_lower:
            specs["gpu"] = "Integrated"

    # Extract OS (handle partial matches)
    os_match = re.search(r"(windows(?:\s*\d+)?|win\s*\d+|mac\s*os|jioos)", name_lower, re.IGNORECASE)
    if os_match:
        os_value = os_match.group(1).strip()
        if "win" in os_value.lower() and "windows" not in os_value.lower():
            os_value = os_value.replace("win", "windows").strip()
        if os_value.lower() == "windows":
            os_value = "windows 11"
        specs["os"] = os_value

    # Extract weight
    weight_match = re.search(r"(\d+\.?\d*)\s*kg", name_lower, re.IGNORECASE)
    if weight_match:
        specs["weight"] = weight_match.group(1) + " kg"

    # Extract resolution
    resolution_match = re.search(r"(fhd|wuxga|qhd|2k|4k|\d+x\d+)", name_lower, re.IGNORECASE)
    if resolution_match:
        resolution = resolution_match.group(1).upper()
        if "4k" in resolution.lower() and "144hz" in name_lower:
            resolution = "FHD"  # Downgrade to FHD if 4K seems unlikely
        specs["resolution"] = resolution

    # Debug print to see what specs were extracted
    print(f"Extracted specs from name '{name}': {specs}")
    return specs

def matches_requirements(product, requirements):
    """Check if a product matches the customer's requirements with debug logging."""
    specs = product["specifications"]
    price = product["price"]

    # Check price
    try:
        price_value = float(price.replace("₹", "").replace(",", ""))
        if "max_price" in requirements and price_value > requirements["max_price"]:
            print(f"Product '{product['name']}' rejected: Price {price_value} exceeds max_price {requirements['max_price']}")
            return False
    except (ValueError, AttributeError):
        print(f"Product '{product['name']}' rejected: Unable to parse price '{price}'")
        return False

    # Check critical specs (processor, ram, ssd)
    critical_specs = ["processor", "ram", "ssd"]
    for key in critical_specs:
        if key not in requirements:
            continue
        if key not in specs or specs[key] == "N/A":
            print(f"Product '{product['name']}' rejected: {key} is N/A")
            return False
        product_value = specs[key].lower()
        required_value = str(requirements[key]).lower()

        if key == "processor":
            if required_value not in product_value:
                print(f"Product '{product['name']}' rejected: {key} '{product_value}' does not contain '{required_value}'")
                return False
        elif key == "ram" or key == "ssd":
            try:
                product_match = re.search(r"(\d+)\s*(gb|tb)", product_value, re.IGNORECASE)
                required_match = re.search(r"(\d+)\s*(gb|tb)", required_value, re.IGNORECASE)
                if not product_match or not required_match:
                    print(f"Product '{product['name']}' rejected: Failed to parse {key} - product: '{product_value}', required: '{required_value}'")
                    return False
                product_num = float(product_match.group(1))
                required_num = float(required_match.group(1))
                product_unit = product_match.group(2).upper()
                required_unit = required_match.group(2).upper()
                if product_unit == "TB":
                    product_num *= 1000
                if required_unit == "TB":
                    required_num *= 1000
                if product_num < required_num:
                    print(f"Product '{product['name']}' rejected: {key} {product_num}GB is less than required {required_num}GB")
                    return False
            except (AttributeError, ValueError):
                print(f"Product '{product['name']}' rejected: Failed to compare {key} - product: '{product_value}', required: '{required_value}'")
                return False

    # Check non-critical specs (e.g., weight, gpu, os, resolution)
    for key, value in requirements.items():
        if key in critical_specs or key == "max_price":
            continue
        if key not in specs or specs[key] == "N/A":
            continue  # Skip non-critical specs if not found
        product_value = specs[key].lower()
        required_value = str(value).lower()

        if key == "weight":
            try:
                product_num = float(re.search(r"\d+\.?\d*", product_value).group())
                required_num = float(re.search(r"\d+\.?\d*", required_value).group())
                if product_num > required_num:
                    print(f"Product '{product['name']}' rejected: {key} {product_num} kg exceeds required {required_num} kg")
                    return False
            except (AttributeError, ValueError):
                print(f"Product '{product['name']}' rejected: Failed to compare {key} - product: '{product_value}', required: '{required_value}'")
                return False
        elif key == "gpu" or key == "os" or key == "resolution":
            if required_value not in product_value:
                print(f"Product '{product['name']}' rejected: {key} '{product_value}' does not contain '{required_value}'")
                return False

    print(f"Product '{product['name']}' accepted")
    return True

def search_flipkart(query, requirements, max_results=10, max_pages=5):
    """Search Flipkart for products based on the query and filter by requirements."""
    products = []
    seen_names = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        user_agent = random.choice(USER_AGENTS)
        context = browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()

        current_page = 1
        while current_page <= max_pages and len(products) < max_results:
            try:
                search_url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}&page={current_page}"
                print(f"Scraping page {current_page}: {search_url}")
                page.goto(search_url, timeout=30000)
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(5000)
            except Exception as e:
                print(f"Failed to load search page {current_page} for query '{query}': {e}")
                break

            items = page.query_selector_all("div.KzDlHZ, div.tUxRFH")
            product_data = []
            for item in items:
                try:
                    name_element = item.query_selector("div.KzDlHZ, a.IRpwTa")
                    price_element = item.query_selector("div.Nx9bqj, div.yRaYxA")
                    rating_element = item.query_selector("div.XQDdHH, span.sGWbFc")
                    link_element = item.query_selector("a.CGtC98, a.IRpwTa")

                    name = name_element.text_content().strip() if name_element else "N/A"
                    price = price_element.text_content().strip() if price_element else "N/A"
                    rating = rating_element.text_content().strip() if rating_element else "N/A"
                    link = link_element.get_attribute("href") if link_element else "N/A"

                    if name == "N/A" or "page" in name.lower():
                        continue

                    if "laptop" in query.lower() and ("desktop" in name.lower() or "computer pc" in name.lower()):
                        print(f"Skipping desktop product: {name}")
                        continue

                    if name in seen_names:
                        continue
                    seen_names.add(name)

                    if link != "N/A":
                        link = link if link.startswith("https://") else f"https://www.flipkart.com{link}"

                    product_data.append({
                        "name": name,
                        "price": price,
                        "rating": rating,
                        "link": link
                    })

                except Exception as e:
                    print(f"Error processing item: {e}")
                    continue

            for data in product_data:
                if len(products) >= max_results:
                    break

                if not data["link"].startswith("https://www.flipkart.com") or "#" in data["link"]:
                    print(f"Skipping malformed link for {data['name']}: {data['link']}")
                    continue

                # Extract specs from both name and link
                detailed_specs = extract_specs_from_name(data["name"], data["link"])

                product = {
                    "site": "Flipkart",
                    "category": "laptop" if "laptop" in query.lower() else "phone",
                    "name": data["name"],
                    "price": data["price"],
                    "rating": data["rating"],
                    "link": data["link"],
                    "specifications": detailed_specs
                }

                if matches_requirements(product, requirements):
                    products.append(product)

            current_page += 1
            next_page_button = page.query_selector("a._9QVEpD span:has-text('Next')")
            if not next_page_button:
                break
            time.sleep(random.uniform(2, 4))

        context.close()
        browser.close()

    products.sort(key=lambda x: float(x["price"].replace("₹", "").replace(",", "")) if x["price"] != "N/A" else float("inf"))
    return products

if __name__ == "__main__":
    customer_query = "laptop with i7 processor 16GB RAM 1TB SSD"
    requirements = {
        "processor": "i7",
        "ram": "16GB",
        "ssd": "1TB",
        "max_price": 150000
    }

    print(f"Searching for: {customer_query}")
    results = search_flipkart(customer_query, requirements, max_results=10, max_pages=5)
    print(f"Found {len(results)} matching products:")
    for product in results:
        print(json.dumps(product, indent=2))

    os.makedirs("data", exist_ok=True)
    with open("data/flipkart_results.json", "w") as f:
        json.dump(results, f, indent=2)