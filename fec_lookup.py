import json
import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter, Retry
from textpack import tp

fec_api_key = '***REMOVED***'
url_params = '&per_page=100&&min_amount=1000'

s = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[ 502, 503, 504 ])
s.mount('https://', HTTPAdapter(max_retries=retries))

# Accept a comma separated list of FEC Committee IDs
committee_ids_raw = 'C00791525, C00588772, C00410803, C00663658, C00768101'
# Split by comma
commitee_ids_raw = committee_ids_raw.split(',')
# Strip out white space
commitee_ids_raw = map(str.strip, commitee_ids_raw)
# Use set to dedupe and set as an immutable tuple
committee_ids = tuple(set(commitee_ids_raw))

print(f"Fetching FEC Data for committees")

master_df = pd.DataFrame()

for c in committee_ids:

    fundraisers_list = []

    comm_request_url = f"https://api.open.fec.gov/v1/committee/{c}/?sort_nulls_last=false&sort_hide_null=false&page=1&sort_null_only=false&api_key={fec_api_key}&per_page=20&sort=name"
    comm_info = s.get(comm_request_url).json()
    comm_info['results']
    committee_name = comm_info['results'][0]['name']
    print(f"Fetching data for {committee_name}")

    request_url = f"https://api.open.fec.gov/v1/schedules/schedule_b/?sort_hide_null=false&sort_null_only=false&api_key={fec_api_key}&committee_id={c}&disbursement_description=Fundraising&disbursement_description=Fundrais%25&disbursement_description=fundraising&disbursement_description=fundrais%25&per_page=20&sort=-disbursement_date{url_params}"
    response_info = s.get(request_url).json()

    page_max = response_info['pagination']['count']

    # If more than one page, keep getting data until we run out
    if page_max > 1:

        latest_results = response_info
        
        # Grab page one results
        for results in latest_results['results']:
            fundraisers_list.append([results['recipient_name'],results['disbursement_amount']])

        # Grab all the other pages of results
        while len(latest_results['results']) != 0:
            last_index = latest_results['pagination']['last_indexes']['last_index']
            last_disbursement_date = latest_results['pagination']['last_indexes']['last_disbursement_date']
            # Build next page URL
            next_request_url = f"{request_url}&last_index={last_index}&last_disbursement_date={last_disbursement_date}"
            # Ask for the next page of JSON data
            latest_results = s.get(next_request_url).json()
            # Append more fundraiser names
            for results in latest_results['results']:
                fundraisers_list.append([results['recipient_name'],results['disbursement_amount']])

    # If only one page of results, then produce a list of fundraisers for the committee
    else:
        for results in response_info['results']:
            fundraisers_list.append([results['recipient_name'],results['disbursement_amount']])


    fundraiser_df = pd.DataFrame(data=fundraisers_list, columns=['recipient_name', 'disbursement_amount'])
    fundraiser_df['committee_name'] = committee_name
    fundraiser_df['committee_id'] = c

    master_df = pd.concat([master_df,fundraiser_df])

print("Data collection finished")
print("Grouping recipients across committees")

grouped_text = tp.TextPack(master_df, 'recipient_name', match_threshold=0.70, ngram_remove=r'[,-./]', ngram_length=3)
grouped_text.run()
grouped_text.add_grouped_column_to_data(column_name='Group')

summary_table = master_df.groupby('Group')['committee_name'].agg(['nunique','unique'])
summary_table = summary_table.rename(columns={'unique':'committee(s)','nunique' : 'committee_count'})
print(summary_table[summary_table['committee_count'] > 1])