from playwright.sync_api import sync_playwright
import re
import random
import time
import json

# List of user agents to rotate
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
]

def extract_specs_from_name(name):
    """Extract specifications from the product name."""
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

    # Extract processor
    processor_match = re.search(r"(intel\s*core\s*i[3-9]|i[3-9]|amd\s*ryzen\s*[3-9]|snapdragon|apple\s*m[1-3])[\s\w-]*(?:\d{4,5}[u|h]?)", name_lower, re.IGNORECASE)
    if processor_match:
        specs["processor"] = processor_match.group(0).strip()

    # Extract RAM
    ram_match = re.search(r"(\d{1,2})\s*gb\s*(?:ram|lpddr|ddr)", name_lower, re.IGNORECASE)
    if ram_match:
        specs["ram"] = ram_match.group(1) + "GB"

    # Extract SSD
    ssd_match = re.search(r"(\d{1,4})\s*(gb|tb)\s*ssd", name_lower, re.IGNORECASE)
    if ssd_match:
        size = ssd_match.group(1)
        unit = ssd_match.group(2).upper()
        specs["ssd"] = f"{size}{unit}"

    # Extract display size (improved regex)
    display_match = re.search(r"(\d{1,2}(?:\.\d)?)\s*(?:inch|cm|['\"])\s*(?:display|screen|fhd|wuxga|qhd)?", name_lower, re.IGNORECASE)
    if display_match:
        size = float(display_match.group(1))
        unit = display_match.group(0).lower()
        if "cm" in unit:
            size = round(size / 2.54, 1)  # Convert cm to inches
        specs["display_size"] = f"{size} inch"

    # Extract GPU
    gpu_match = re.search(r"(nvidia\s*geforce|rtx|amd\s*radeon|iris\s*xe|adreno)", name_lower, re.IGNORECASE)
    if gpu_match:
        specs["gpu"] = gpu_match.group(0).strip()
    elif "integrated" in name_lower:
        specs["gpu"] = "Integrated"

    # Extract OS (fixed typo)
    os_match = re.search(r"(windows\s*\d+|win\s*\d+|mac\s*os|jioos)", name_lower, re.IGNORECASE)
    if os_match:
        os_value = os_match.group(1).strip()
        if "win" in os_value.lower():
            os_value = os_value.replace("win", "windows").strip()
        # Ensure no duplicate "windows"
        os_value = re.sub(r"windows\s*windows", "windows", os_value, flags=re.IGNORECASE)
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

    return specs

def extract_specs_from_page(page, product_name, retries=2):
    """Extract structured specs from the product page with retries."""
    specs = extract_specs_from_name(product_name)  # Start with specs from name

    for attempt in range(retries + 1):
        try:
            # Wait for DOM content to load
            page.wait_for_load_state("domcontentloaded", timeout=60000)

            # Wait for the product details section to load
            selectors = ["#prodDetails", "#feature-bullets"]
            spec_container = None
            for selector in selectors:
                try:
                    page.wait_for_selector(selector, timeout=20000, state="visible")
                    spec_container = page.query_selector(selector)
                    if spec_container:
                        print(f"Found container using selector: {selector}")
                        break
                except Exception as e:
                    print(f"Selector {selector} failed: {e}")
                    continue

            if not spec_container:
                print(f"Timeout waiting for product details on page {page.url}")
                return specs

            # Extract from #prodDetails
            if spec_container.get_attribute("id") == "prodDetails":
                try:
                    page.wait_for_selector("#productDetails_techSpec_section_1", timeout=10000, state="visible")
                    spec_table = spec_container.query_selector("#productDetails_techSpec_section_1")
                    if spec_table:
                        print("Found technical details table: #productDetails_techSpec_section_1")
                        rows = spec_table.query_selector_all("tr")
                        for row in rows:
                            th = row.query_selector("th")
                            td = row.query_selector("td")
                            if not th or not td:
                                continue
                            label = th.text_content().strip().lower()
                            value = td.text_content().strip()
                            print(f"Found spec: {label} = {value}")  # Debug print

                            if "processor type" in label:
                                specs["processor"] = value
                            elif "ram size" in label or "memory technology" in label:
                                ram_match = re.search(r"(\d+)\s*gb", value, re.IGNORECASE)
                                if ram_match:
                                    specs["ram"] = ram_match.group(1) + "GB"
                            elif "hard drive size" in label or "hard disk description" in label:
                                ssd_match = re.search(r"(\d+)\s*(gb|tb)", value, re.IGNORECASE)
                                if ssd_match:
                                    size = ssd_match.group(1)
                                    unit = ssd_match.group(2).upper()
                                    specs["ssd"] = f"{size}{unit}"
                            # In extract_specs_from_page, updated display size extraction
                            elif "standing screen display size" in label:
                                display_match = re.search(r"(\d+\.?\d*)\s*(?:inch(?:es)?|cm|centimetres)", value, re.IGNORECASE)
                                if display_match:
                                    size = float(display_match.group(1))
                                    unit = display_match.group(0).lower()
                                    if "cm" in unit or "centimetres" in unit:
                                        size = round(size / 2.54, 1)  # Convert cm to inches
                                    specs["display_size"] = f"{size} inch"
                                else:
                                    print(f"Failed to parse display size: {value}")
                            elif "graphics card description" in label or "graphics coprocessor" in label:
                                if "integrated" in value.lower():
                                    specs["gpu"] = "Integrated"
                                else:
                                    gpu_match = re.search(r"(nvidia\s*geforce|rtx|amd\s*radeon|iris xe|adreno)[\s\w]*(?:\d{3,4})?", value, re.IGNORECASE)
                                    if gpu_match:
                                        specs["gpu"] = gpu_match.group(0).strip()
                            elif "operating system" in label:
                                os_match = re.search(r"(windows\s*\d+|mac\s*os|jioos)", value, re.IGNORECASE)
                                if os_match:
                                    os_value = os_match.group(1).strip()
                                    # Fix any potential typos
                                    os_value = re.sub(r"windows\s*windows", "windows", os_value, flags=re.IGNORECASE)
                                    specs["os"] = os_value
                            elif "item weight" in label:
                                weight_match = re.search(r"(\d+\.?\d*)\s*kg", value, re.IGNORECASE)
                                if weight_match:
                                    specs["weight"] = weight_match.group(1) + " kg"
                            elif "average battery life" in label:
                                battery_match = re.search(r"(\d+)\s*hours", value, re.IGNORECASE)
                                if battery_match:
                                    specs["battery"] = battery_match.group(1) + " Hours"
                            elif "resolution" in label:
                                resolution_match = re.search(r"(fhd|wuxga|qhd|2k|4k|\d+x\d+)", value, re.IGNORECASE)
                                if resolution_match:
                                    specs["resolution"] = resolution_match.group(1).upper()
                except Exception as e:
                    print(f"Failed to find or parse #productDetails_techSpec_section_1: {e}")

            # Extract from #feature-bullets
            if spec_container.get_attribute("id") == "feature-bullets":
                text_content = spec_container.text_content().lower()
                display_match = re.search(r"(\d+\.?\d*)\s*(?:inch|cm)\s*(?:display|screen)", text_content, re.IGNORECASE)
                if display_match and specs["display_size"] == "N/A":
                    size = float(display_match.group(1))
                    unit = display_match.group(0).lower()
                    if "cm" in unit:
                        size = round(size / 2.54, 1)  # Convert cm to inches
                    specs["display_size"] = f"{size} inch"

                os_match = re.search(r"(windows\s*\d+|mac\s*os|jioos)", text_content, re.IGNORECASE)
                if os_match and specs["os"] == "N/A":
                    os_value = os_match.group(1).strip()
                    os_value = re.sub(r"windows\s*windows", "windows", os_value, flags=re.IGNORECASE)
                    specs["os"] = os_value

                weight_match = re.search(r"(\d+\.?\d*)\s*kg", text_content, re.IGNORECASE)
                if weight_match and specs["weight"] == "N/A":
                    specs["weight"] = weight_match.group(1) + " kg"

                resolution_match = re.search(r"(fhd|wuxga|qhd|2k|4k|\d+x\d+)", text_content, re.IGNORECASE)
                if resolution_match and specs["resolution"] == "N/A":
                    specs["resolution"] = resolution_match.group(1).upper()

            break  # Successful extraction, exit retry loop

        except Exception as e:
            print(f"Attempt {attempt + 1} failed for {page.url}: {e}")
            if attempt < retries:
                print(f"Retrying... ({attempt + 1}/{retries})")
                time.sleep(random.uniform(2, 5))
                page.reload()
                continue
            else:
                print(f"All retries failed for {page.url}. Using specs from name.")
                break

    return specs

def matches_requirements(product, requirements):
    """Check if a product matches the customer's requirements."""
    specs = product["specifications"]
    price = product["price"]

    # Check price
    try:
        price_value = float(price.replace("₹", "").replace(",", ""))
        if "max_price" in requirements and price_value > requirements["max_price"]:
            return False
    except (ValueError, AttributeError):
        return False  # Skip if price can't be parsed

    # Check critical specs (processor, ram, ssd)
    critical_specs = ["processor", "ram", "ssd"]
    for key in critical_specs:
        if key not in requirements:
            continue
        if key not in specs or specs[key] == "N/A":
            return False
        product_value = specs[key].lower()
        required_value = str(requirements[key]).lower()

        if key == "processor":
            if required_value not in product_value:
                return False
        elif key == "ram" or key == "ssd":
            try:
                product_match = re.search(r"(\d+)\s*(gb|tb)", product_value, re.IGNORECASE)
                required_match = re.search(r"(\d+)\s*(gb|tb)", required_value, re.IGNORECASE)
                if not product_match or not required_match:
                    return False
                product_num = float(product_match.group(1))
                required_num = float(required_match.group(1))
                product_unit = product_match.group(2).upper()
                required_unit = required_match.group(2).upper()
                # Convert to GB for comparison
                if product_unit == "TB":
                    product_num *= 1000
                if required_unit == "TB":
                    required_num *= 1000
                if product_num < required_num:
                    return False
            except (AttributeError, ValueError):
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
                    return False
            except (AttributeError, ValueError):
                return False
        elif key == "gpu" or key == "os" or key == "resolution":
            if required_value not in product_value:
                return False

    return True

def search_amazon(query, requirements, max_results=10, max_pages=5):  # Increased to 5 pages
    """Search Amazon for products based on the query and filter by requirements."""
    products = []
    seen_names = set()  # To track duplicates
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
            # Perform the search
            try:
                search_url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}&page={current_page}"
                print(f"Scraping page {current_page}: {search_url}")
                page.goto(search_url, timeout=30000)
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(5000)
            except Exception as e:
                print(f"Failed to load search page {current_page} for query '{query}': {e}")
                break

            # Collect product data from search results
            items = page.query_selector_all(".s-result-item, .s-card-container")
            product_data = []
            for item in items:
                try:
                    if item.query_selector(".s-sponsored-label") or item.query_selector(".s-pagination-item"):
                        continue
                except Exception:
                    continue

                name_element = item.query_selector("h2 a span, .a-text-normal")
                price_element = item.query_selector(".a-price-whole, .a-price .a-offscreen")
                rating_element = item.query_selector(".a-icon-alt, span[aria-label*='out of 5 stars']")
                link_element = item.query_selector("a.a-link-normal")

                name = name_element.text_content().strip() if name_element else "N/A"
                price = price_element.text_content().replace(",", "").strip() if price_element else "N/A"
                rating = rating_element.text_content().strip() if rating_element else "N/A"
                link = link_element.get_attribute("href") if link_element else "N/A"

                if name == "N/A" or "page" in name.lower() or "buying options" in name.lower():
                    continue

                # Skip desktops if the query is for laptops
                if "laptop" in query.lower() and ("desktop" in name.lower() or "computer pc" in name.lower()):
                    print(f"Skipping desktop product: {name}")
                    continue

                if name in seen_names:
                    continue
                seen_names.add(name)

                if link != "N/A":
                    link = link if link.startswith("https://") else f"https://www.amazon.in{link}"

                product_data.append({
                    "name": name,
                    "price": price,
                    "rating": rating,
                    "link": link
                })

            # Process the products on this page
            for i, data in enumerate(product_data):
                if len(products) >= max_results:
                    break

                # Skip if the link is malformed
                if not data["link"].startswith("https://www.amazon.in") or "#" in data["link"]:
                    print(f"Skipping malformed link for {data['name']}: {data['link']}")
                    continue

                # Extract initial specs from name
                detailed_specs = extract_specs_from_name(data["name"])

                # Visit product page only for the top 3 matches per page to confirm critical specs
                if i < 3:
                    max_attempts = 2
                    for attempt in range(max_attempts):
                        try:
                            product_page = context.new_page()
                            product_page.goto(data["link"], timeout=30000)
                            product_page.wait_for_load_state("domcontentloaded")
                            detailed_specs = extract_specs_from_page(product_page, data["name"])
                            product_page.close()
                            time.sleep(random.uniform(1, 3))  # Random delay to avoid bot detection
                            break
                        except Exception as e:
                            print(f"Attempt {attempt + 1} failed to scrape product page for {data['name']}: {e}")
                            if attempt < max_attempts - 1:
                                print(f"Retrying with a different user agent... ({attempt + 1}/{max_attempts})")
                                context = browser.new_context(
                                    user_agent=random.choice(USER_AGENTS),
                                    viewport={"width": 1280, "height": 720}
                                )
                                time.sleep(random.uniform(2, 5))
                                continue
                            else:
                                print(f"All attempts failed for {data['name']}. Using specs from name.")

                product = {
                    "site": "Amazon",
                    "category": "laptop" if "laptop" in query.lower() else "phone",
                    "name": data["name"],
                    "price": data["price"] if data["price"] != "N/A" else "N/A",
                    "rating": data["rating"],
                    "link": data["link"],
                    "specifications": detailed_specs
                }

                # Filter based on requirements
                if matches_requirements(product, requirements):
                    products.append(product)

            # Check for next page
            current_page += 1
            next_page_button = page.query_selector("a.s-pagination-next")
            if not next_page_button or "s-pagination-disabled" in next_page_button.get_attribute("class"):
                break

        context.close()
        browser.close()

    # Sort products by price
    products.sort(key=lambda x: float(x["price"].replace("₹", "").replace(",", "")) if x["price"] != "N/A" else float("inf"))
    return products

if __name__ == "__main__":
    # Example customer query and requirements
    customer_query = "laptop with i5 processor 4GB graphics 16GB RAM"
    requirements = {
        "processor": "i5",
        "ram": "16GB",
        "gpu": "4GB",
        "max_price": 150000
    }

    print(f"Searching for: {customer_query}")
    results = search_amazon(customer_query, requirements, max_results=10, max_pages=5)
    print(f"Found {len(results)} matching products:")
    for product in results:
        print(json.dumps(product, indent=2))

    # Save results to a file
    with open("data/amazon_results.json", "w") as f:
        json.dump(results, f, indent=2)