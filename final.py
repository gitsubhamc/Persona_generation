import requests
from bs4 import BeautifulSoup
import openai
import re
import facebook
from pymongo import MongoClient
client = MongoClient('localhost', 27017)
db = client['property_types']



def fetch_product_description(url_or_text):
    if url_or_text.startswith("http"):
        response = requests.get(url_or_text)
        soup = BeautifulSoup(response.text, 'html.parser')
        product_description = soup.get_text()
    else:
        product_description = url_or_text
    return product_description

def extract_information_gpt(description):
    prompt = f"""
    Extract the following details from the product description:
    1. Category: The overall category of the product.
    2. Product: The specific product name or type.
    3. Nature: Key attributes including:
       - Product Type (e.g., residential, commercial)
       - Location (e.g., city, country)
       - Differentiating Features (e.g., luxury, eco-friendly, innovative features)

    Ensure the response is formatted exactly as follows:
    Category: <category>
    Product: <product>
    Nature:
      - Product Type: <product type>
      - Location: <location>
      - Differentiating Features: <differentiating features>

    Product Description:
    {description}
    """
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a facebook assistant find these values efficiently"},
            {"role": "user", "content": prompt}
        ]
    )
    text = response.choices[0].message['content'].strip()
    lines = text.split("\n")
    category = next((line.split(": ")[1].strip() for line in lines if line.startswith("Category:")), None)
    product = next((line.split(": ")[1].strip() for line in lines if line.startswith("Product:")), None)
    nature = {}
    for line in lines:
        if line.strip().startswith("- Product Type:"):
            nature['Product Type'] = line.split(": ")[1].strip()
        elif line.strip().startswith("- Location:"):
            nature['Location'] = line.split(": ")[1].strip()
        elif line.strip().startswith("- Differentiating Features:"):
            nature['Differentiating Features'] = line.split(": ")[1].strip()
    
    if "real" or "estate" or "real estate" in category.lower():
        category='real_estate'

    return category, product, nature


def generate_personas(category, product, nature):
    prompt = (
        f"Given the category: {category}, product: {product}, and nature: {nature}, generate detailed personas for potential customers in the real estate market. "
        "Each persona should have the following structure:\n\n"
        "Persona {n}:\n"
        "Role: {role}\n"
        "Description: {description}\n"
        "Use only the base version of the interests (e.g., 'Technology' instead of 'Innovative home automation technology'). Aim for at least 15-20 items.\n"
        "Create 5 personas.\n\n"
        "Output format:\n"
        "Persona {n}:\n"
        "Role: \n"
        "Description: \n"
        "Interests:\n"
        "1. \n"
        "2. \n"
        "...\n"
    )
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a facebook blueprint certified professional and you have been assigned the task to identify persona of consumer groups who are most likely to buy the foresaid product."},
            {"role": "user", "content": prompt}
        ]
    )
    # return response.choices[0].message['content'].strip()
    return response.choices[0].message['content'].strip()


def parse_personas(text):
    personas = []
    persona_blocks = text.split("Persona ")[1:6]  # Slice to limit to 3 personas
    for i, block in enumerate(persona_blocks):
        lines = block.strip().split("\n")
        
        # Extracting persona name, role, and description
        role_line = lines[1].strip()
        role = role_line.split(": ")[-1]  # Extracting role from "Role: Young Professional"
        
        description_line = lines[2].strip()
        description = description_line.split(": ")[-1]  # Extracting description from "Description: Aspiring individual..."
        
        try:
            interests_start = lines.index("Interests:") + 1
        except ValueError:
            interests_start = len(lines)
        # demographics_start = lines.index("Demographics:")
        
        interests = []
        for i in range(interests_start, len(lines)):
            line = lines[i].strip()
            if line.startswith(f"{i - interests_start + 1}. "):
                interest = line.split(". ", 1)[1].strip()
                interests.append(interest)
            else:
                break        
        # demographics = [line.replace(f"{i}. ", "").strip() for i, line in enumerate(lines[demographics_start + 1:], 1) if line.startswith(f"{i}. ")]
        
        personas.append({
            "Persona Name": role,
            "Role": role,
            "Description": description,
            "Interests": interests,
            # "Demographics": demographics
        })
    return personas

def type_casting_name_ids(interests,Role,category):
    # # Fetch interest IDs
    graph = facebook.GraphAPI(access_token=access_token, version='3.1')
    interest_ids = []
    for interest in interests:
       try:
           response = graph.get_object(f'search?type=adinterest&q={interest}')
           print()
           if 'data' in response:
               for item in response['data']:
                   interest_ids.append(item['id'])
       except facebook.GraphAPIError as e:
           print(f"Error fetching targeting options for {interest}: {e}")


    print("Interest IDs:", interest_ids)


    # Validate interest IDs
    valid_interest_ids = []
    for interest_id in interest_ids:
       try:
           response = graph.get_object(interest_id)
           valid_interest_ids.append(interest_id)
       except facebook.GraphAPIError as e:
           print(f"Invalid interest ID: {interest_id}")


    print("Valid Interest IDs:", valid_interest_ids)


    interest_terms = {}
    for valid_id in valid_interest_ids:
       try:
           response = graph.get_object(f"{valid_id}?fields=name")
           interest_terms[valid_id] = response['name']
       except facebook.GraphAPIError as e:
           print(f"Error fetching interest term for ID {valid_id}: {e}")
    print(f"THe DICT is-------------->{interest_terms}-----------")
    print("Interest Terms:")
    for interest_id, term in interest_terms.items():
       print(f"{interest_id}: {term}")

    prompt = f"Filter out irrelevant interests from the following list based on their names. Only keep those related to the product category '{category}' and the role '{Role}'. Remove any leading characters like '-' or spaces:\n\n"
    for interest_id, term in interest_terms.items():
        prompt += f"{interest_id}: {term}\n"
    prompt += "\nRelevant Interests:"

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # Or the appropriate model engine
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=150,
        n=1,
        stop=None,
        temperature=0.5,
    )
    print(f"THE resis --->{response}")
    filtered_terms = response['choices'][0]['message']['content'].strip().split('\n')
    processed_filtered_terms = []
    for term in filtered_terms:
        clean_term = term.strip('- ').strip()
        if clean_term.startswith("Relevant Interests:"):
            pass
        else:
            processed_filtered_terms.append(clean_term)
    filtered_terms=processed_filtered_terms
    print(f"THe filtered--->{filtered_terms}--")
    # # Filter relevant interests using the function
    final_intrest_name_id=[]
    relevant_interest_terms = filtered_terms
    print(f'relevant--{relevant_interest_terms}')
    for term in relevant_interest_terms:
        for key, val in interest_terms.items():
            if term == val:
                final_intrest_name_id.append({"id": key, "name": val})
    ##########hiting the adset##########
    exclusions=list(db['real_estate_exclusions'].find({},{'_id':0,'id':1,'term':1}))
    formatted_exclusions = [{'id': exclusion['id'], 'name': exclusion['term']} for exclusion in exclusions]
    print(f"-exclusion list--{formatted_exclusions}----------------")
    print(f"--formated intrests--{final_intrest_name_id}------------")
    

    import requests
    import json

    url = "https://graph.facebook.com/v20.0/act_1485767852038030/adsets"

    payload = json.dumps({
    "access_token": "EAAUBOprDfKsBO76DsNI5ThYZCB91LF7yOhvwg5xIsVg5eqODRTsPRZAhoRnr5TRqGbw46DvgCEtqvH1kKAPwIHfRi9oweF86sUzNlf0JOr44yOesbfbWfQZATkv9cBypV3CRoxMcnZBCSy29oE3NVW0rZCRInKFvJTZBWdVPFq4zWGwqiRP2QQlcRW5QbpaBa3",
    "bid_amount": 200,
    "billing_event": "IMPRESSIONS",
    "campaign_id": "120211203418760471",
    "daily_budget": 10000,
    "name": "Summer Sale Ad Set",
    "optimization_goal": "LEAD_GENERATION",
    "destination_type": "ON_AD",
    "promoted_object": {
        "page_id": "337381279463080"
    },
    "status": "ACTIVE",
    "targeting": {
    "geo_locations": {
      "countries": [
        "IN"
      ]
    },
    "age_min": 18,
    "age_max": 65,
    "genders": [
      1,
      2
    ],
    "flexible_spec": [
      {
        "interests": final_intrest_name_id
      }
    ],
    "exclusions": {
      "interests": formatted_exclusions
    }
    }
    })





    print(f"THE payload is ------>{payload}--")
    headers = {
    'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    print(response.text)
    return response.text





def main():
    url_or_brochure = input("Enter URL or brochure: ")
    product_description=fetch_product_description(url_or_brochure)
    category, product, nature=extract_information_gpt(product_description)
    persona=generate_personas(category,product,nature)
    print(f"persona------->{persona}")
    ordered_persona=parse_personas(persona)
    print(f"THe ordered persona is ------->{ordered_persona}")
    for i, persona in enumerate(ordered_persona):
        print(f"Persona {i + 1}:\nRole: {persona['Role']}\nDescription: {persona['Description']}\n")
    choice = int(input("Please select a persona (1, 2, or 3): "))
    print(f"--------{ordered_persona[choice-1]['Interests']}")
    adset_creation=type_casting_name_ids(ordered_persona[choice-1]['Interests'],ordered_persona[choice-1]['Role'],category)
    print(adset_creation)
    




if __name__ == "__main__":
    main()



