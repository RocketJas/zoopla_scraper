import math
import re
import json
import requests
from bs4 import BeautifulSoup
import csv
from datetime import datetime
from datetime import date
import os.path

def solve(s): #Function to remove date ordinals from date         
    return re.sub(r'(\d)(st|nd|rd|th)', r'\1', s)

def data_from_propery_page(url,sale_status):
    # locate the tag
    soup = BeautifulSoup(requests.get(url).content, 'html.parser')
    script = soup.find_all("script")[3]
    # parse some data from script
    property_data = re.findall(r'ZPG\.trackData\.taxonomy = ({.*?});', script.text, flags=re.S)[0]
    property_data = json.loads( re.sub(r'([^"\s]+):\s', r'"\1": ', property_data) )
    #Create postcode from outconde and incode
    property_data["postcode"] = property_data["outcode"]+"-"+property_data["incode"]
    #Create another key-value pair with rental value
    #The location of this depends upon whether the property is for-sale or to-rent
    if (sale_status=="to-rent"):
        try:
            market_rental_value_string = soup.find(class_="dp-market-stats__price ui-text-t4").text
            market_rental_value = re.sub('[^0-9]','', str(market_rental_value_string))
            property_data["rental_value"] = market_rental_value
            rent_per_room = int(property_data["price"])/int(property_data["num_beds"])
            if(rent_per_room<200):
                property_data["rent_per_room"] = property_data["price"]
            else:
                property_data["rent_per_room"] = str(rent_per_room)
        except:
            pass
        
            
    elif (sale_status=="for-sale"):
        market_rental_value_string = soup.find_all(class_="dp-market-stats__price ui-text-t4")
        property_data["rental_value"] = ""
        property_data["yield"] = ""
        if(market_rental_value_string == []):
            pass
        else:
            market_rental_value = re.sub('[^0-9]','', str(market_rental_value_string[-1].text))
            property_data["rental_value"] = market_rental_value
            if((property_data["rental_value"]!= "")&(property_data["price"]!= "")):
                property_data["yield"] = 12*int(property_data["rental_value"])/int(property_data["price"])
                
    property_data["url"] = url
    property_data["id"] = url[-8:]
    try:
        property_data["listing_date"] = datetime.strptime(solve(soup.find(class_="dp-price-history__item-date").text),"%d %b %Y")
    except:
        pass
        
    #Create another key-value pair with 
    
    
    return property_data
    
def all_search_pages_scraper(postcode, radius, sale_status): #sale_status must be exactly "for-sale" or "to-rent"
    property_urls = []
    #Create url of specific zoopla page to search given postcode, radius and page of search
    #Postcoe must be of the form "abc-xyz" and all imputs must be strings
    url = "https://www.zoopla.co.uk/"+sale_status+"/property/"+postcode+"/?identifier="+postcode+"&page_size=100&q="+postcode+"&search_source=refine&radius="+radius+"&pn=1"
    #Use requests to get html of page
    zoopla_search_page_requests = requests.get(url)
    #Create soup object of html
    search_page_soup = BeautifulSoup(zoopla_search_page_requests.text, 'html.parser')
    #Taking a beautiful soup object as imput returns the number of pages to search under the 100 properties per page assumption
    #Make sure only numbers remain, eg 1,324 would not work we need 1324
    properties = search_page_soup.find(class_="search-refine-filters-heading-count").text
    properties_number = int(re.sub('[^0-9]','', properties))
    pages_of_properties = math.ceil(properties_number/100)
    
    
    for page in range(1,pages_of_properties+1):
        #print(type(page))
        #page_str = str(page)
        #Postcoe must be of the form "abc-xyz" and all imputs must be strings
        url = "https://www.zoopla.co.uk/"+sale_status+"/property/"+postcode+"/?identifier="+postcode+"&page_size=100&q="+postcode+"&search_source=refine&radius="+radius+"&results_sort=newest_listings&pn="+str(page)
        #print(url)
        #Use requests to get html of page
        zoopla_search_page_requests = requests.get(url)
        #Create soup object of html
        search_page_soup = BeautifulSoup(zoopla_search_page_requests.text, 'html.parser')    
        #This is just where the data I need is
        correct_script_tag = search_page_soup.find_all("script")[7].text
        id_block_start = re.search("impressions", correct_script_tag).span()[0]
        id_block_end = re.search("pageshow", correct_script_tag).span()[0]
        id_block = correct_script_tag[id_block_start:id_block_end]
        #This gets me all the ids which I will use to gererate web pages of specific properties
        all_numbers = re.findall('[0-9]+', id_block)
        ids = []
        for num in all_numbers:
            if((int(num)>10000000)&(int(num)<99999999)):
                ids.append(num)
        #Generates all the specific property urls from the ids
        
        for i in ids:
            property_urls.append("https://www.zoopla.co.uk/"+sale_status+"/details/"+i)
    return property_urls
    
def make_array_of_property_data(postcode,radius,sale_status):
    search_pages = all_search_pages_scraper(postcode, radius,sale_status)
    print("There are", len(search_pages), "pages to search")
    count = 0
    property_data_array = []
    for page in search_pages:
        property_data_array.append(data_from_propery_page(page,sale_status))
        count = count+1
        print(count, end = ' ')
    return property_data_array

def update_property_data(postcode,radius,sale_status,file_name):
    #open csv file and read contents into list of dictionaries
    if os.path.exists(file_name):
        with open(file_name,newline="") as csvfile:
            csv_opened = csv.DictReader(csvfile)
            csv_list_of_dict = []
            for item in csv_opened:
                csv_list_of_dict.append(dict(item))
        csv_ids = [] 
        #Get ids for properties in csv file for future comparison
        for flat in csv_list_of_dict:
            csv_ids.append(flat.get("listing_id"))
    else:
        csv_ids = []
        csv_list_of_dict = []
        
    search_pages = all_search_pages_scraper(postcode,radius,sale_status)
    search_page_ids = []
    for search_page in search_pages:
        search_page_ids.append(search_page[-8:])
    all_ids = csv_ids + search_page_ids
    new_ids = []
    sold_id_and_dates = []
    for id_ in all_ids:
        if((id_ in csv_ids)&(id_ in search_page_ids)):
            pass
        elif((id_ in csv_ids)&(id_ not in search_page_ids)):
            #property sold
            sold_id_and_dates.append({"id": id_, "date":date})
            for property_ in csv_list_of_dict:
                if((id_ in property_.values())&(property_["sale_status"] == None)):
                    property_["sale_status"] = date.today()
           #USE THIS
           #for i, age in enumerate(d['age'] for d in myList): 
           #print i,age
           #{1: 'Geeks', 2: 'For', 3: 'Geeks'} 
           #find property by id in csv_list_of_dict and append using 
           #csv_list_of_dict[{correct index for property}]["sale_status"] = "Sold"
           #Potentially add in date sold
        elif((id_ in search_page_ids)&(id_ not in csv_ids)):
            #newly listed
            new_ids.append(id_)
    new_urls = []
    for i in new_ids:
        new_urls.append("https://www.zoopla.co.uk/"+sale_status+"/details/"+i)
    print("There are", len(new_urls), "pages to search")
    count = 0
    all_properties = csv_list_of_dict
    for page in new_urls:
        all_properties.append(data_from_propery_page(page,sale_status))
        count = count+1
        print(count, end = ' ')
    #Create new/update excel document
       
    if "sale_status" in all_properties[0]:
        pass
    else:
        all_properties[0]["sale_status"] = None
    
    keys = all_properties[0].keys()
    #print(keys,type(keys))
    with open(file_name, 'w', newline='') as output_file:
        dict_writer = csv.DictWriter(output_file, keys)
        dict_writer.writeheader()
        dict_writer.writerows(all_properties)
        
    return all_properties

#adding a comment here to check how version control works
    


