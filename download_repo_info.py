'''
get_repo_information.py

Downloads information about all GitHub repositories
with greater than or equal to 100 stars and are less than a gigabyte in size 
Each data record has the repository's name, number of stars, and top language
The output is github_repositories.csv
'''

import os
import json
import time
import math
import pickle
import requests
from tqdm import tqdm

#~~~~~~~~~~~~~~~~~~
USER = "noanabeshima"
TOKEN = "14d353dfb27b03c5de0cbe56bab154cf6713dde2"
#~~~~~~~~~~~~~~~~~~


# To ensure we comply with GitHub's Search API rate limit rules
# 30 requests per minute maximum
# https://developer.github.com/v3/#rate-limiting
REMAINING_REQUESTS = 30



def save_ckpt(lower_bound: int, upper_bound: int, repo_list):
    repo_list = list(set(repo_list)) # remove duplicates
    print(f"Saving checkpoint {lower_bound, upper_bound}...")
    with open('repo_ckpt.pkl', 'wb') as f:
        pickle.dump((lower_bound, upper_bound, repo_list), f)

def get_request(lower_bound: int, upper_bound: int, repo_list, page: int = 1):
    # Returns a request object from querying GitHub 
    # for repos in-between size lower_bound and size upper_bound with over 100 stars.
    r = requests.get(
           f'https://api.github.com/search/repositories?q=size:{lower_bound}..{upper_bound}+stars:>100&per_page=100&page={page}',
           auth = (USER, TOKEN)
           )

    if r.status_code == 403:
            print('API rate limit exceeded.')
            save_ckpt(lower_bound, upper_bound, repo_list)
            print('Exiting program.')
            exit()
    elif r.status_code == 422:
        # No more pages available
        return False

    try:
        assert r.status_code == 200
    except:
        print(f'Unexpected status code. Status code returned is {r.status_code}')
        print(r.text)
        save_ckpt(lower_bound, upper_bound, repo_list)
        print("Exiting program.")
        exit()
    
    REMAINING_REQUESTS -= 1

    if REMAINING_REQUESTS == 0:
        print("Sleeping 60 seconds to stay under GitHub API rate limit...")
        time.sleep(60)
        save_ckpt(lower_bound, upper_bound, repo_list)
        REMAINING_REQUESTS = 30

    return r


def download_range(lower_bound, upper_bound, repo_list):
    # Saves the names of repositories on GitHub to repo_list
    # in-between size minimum and maximum with over 100 stars.
    # Github page options start at index 1.
    for page in range(1, 11):
        r = get_request(lower_bound=lower_bound, upper_bound=upper_bound, repo_list=repo_list, page=page)

        if page == 1:
            n_results = r.json()['total_count']
            n_query_pages = min(math.ceil(n_results/100), 10) # GitHub API capped at 1000 results

        for repository in r.json()['items']:
            name = repository['full_name']
            stars = repository['stargazers_count']
            lang = repository['language']
            repo_list.append((name, stars, lang)) # eg (noanabeshima/github-scraper, 1, Python)

        if page >= n_query_pages:
            # No more pages available
            return n_results

if __name__ == '__main__':
    # If pickled checkpoint exists, load it.
    # Otherwise, intialize repo_list as an empty list
    if 'repo_ckpt.pkl' in os.listdir():
        # Load checkpoint
        with open('repo_ckpt.pkl', 'rb') as f:
            lower_bound, upper_bound, repo_list = pickle.load(f)
        print(f"Loading from {lower_bound}..{upper_bound}")
    else:
        lower_bound = 0
        upper_bound = 5
        repo_list = []

    if lower_bound >= 10000000:
        print('''
Checkpoint is for an already completed download of GitHub repository information.
Please delete `repo_ckpt.pkl` to restart and try again.
            ''')
        exit()

    
    r = get_request(lower_bound, upper_bound, repo_list)

    # Initial number of results
    n_results = r.json()['total_count']
    # Initial slope for our linear approximation.
    slope = n_results/(upper_bound-lower_bound)

    # Main loop.
    # Breaks when all repositories considered are greater in size than a gigabyte
    while lower_bound < 10000000:
        # Search for a range of repository sizes
        # from the current lower bound that has <= 1000 repositories
        while True:
            # Update upper bound to be guess by linear approximation for what range will return 1000 results
            # As GitHub repositories follow a power distribution, this tends to be an underestimate.
            upper_bound = math.floor((1000/slope) + lower_bound)
            upper_bound = max(upper_bound, lower_bound + 1)

            # How many results are there at our guess?
            n_results = get_request(lower_bound, upper_bound).json()['total_count']

            # Update the slope of our linear approximation
            slope = n_results/(upper_bound - lower_bound)

            print(f'size {lower_bound}..{upper_bound} ~> {n_results} results')
            # If we get <= 1000 results over the range, exit the search loop
            # and download all repository names over the range
            if n_results <= 1000:
                break

        print(f"Downloading repositories in size range {lower_bound}..{upper_bound}")
        download_range(lower_bound, upper_bound, repo_list)
        lower_bound = upper_bound + 1

    save_ckpt(lower_bound, upper_bound)

    with open('github_repositories.csv', 'w') as f:
        for repo in repo_list:
            name, stars, lang = repo
            f.write(f'{name},{stars},{lang}\n')
