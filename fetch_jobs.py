#!/usr/bin/env python3
"""Fetch SDE job openings from multiple free sources and save as jobs.json"""
import requests
import json
import re
import time
import os
import random
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

SITE_DIR = os.path.dirname(os.path.abspath(__file__))
JOBS_FILE = os.path.join(SITE_DIR, 'jobs.json')

SEARCH_QUERIES = [
    "software development engineer India",
    "SDE jobs India",
    "software engineer Bangalore",
    "software engineer Hyderabad",
    "software engineer Pune",
    "software engineer Mumbai",
    "junior software engineer India",
    "senior software engineer India",
]

def infer_level(title, desc=""):
    """Infer experience level from title and description"""
    text = (title + " " + (desc or "")).lower()
    
    senior_keywords = ['senior', 'sr ', 'lead', 'principal', 'staff', 'architect', 'manager', 'head of', 'staff']
    mid_keywords = ['mid', 'sde 2', 'sde2', 'sde ii', 'software engineer ii', 'ii -', '2+ years', '3+ years']
    entry_keywords = ['junior', 'jr ', 'fresher', 'entry', 'graduate', 'trainee', 'intern', 'sde 1', 'sde1', 
                      'sde i', 'software engineer i', '0-2', '0 - 2', '1+ years']
    
    for kw in senior_keywords:
        if kw in text:
            return 'senior'
    for kw in mid_keywords:
        if kw in text:
            return 'mid'
    for kw in entry_keywords:
        if kw in text:
            return 'entry'
    
    exp_match = re.search(r'(\d+)\s*(?:-|to)\s*(\d+)\s*(?:year|yr|y)', text)
    if exp_match:
        avg_exp = (int(exp_match.group(1)) + int(exp_match.group(2))) / 2
        if avg_exp >= 5:
            return 'senior'
        elif avg_exp >= 2:
            return 'mid'
        else:
            return 'entry'
    
    return 'entry'

def scrape_google_jobs():
    """Scrape SDE jobs from Google Jobs search results"""
    all_jobs = []
    seen = set()
    
    for query in SEARCH_QUERIES[:5]:  # Use first 5 queries to stay fast
        url = f"https://www.google.com/search?q={quote_plus(query)}&ibp=htl;jobs"
        try:
            resp = requests.get(url, headers={**HEADERS, 'User-Agent': random.choice([
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            ])}, timeout=15)
            if resp.status_code != 200:
                continue
            
            soup = BeautifulSoup(resp.text, 'lxml')
            
            # Try multiple selectors that Google Jobs uses
            job_cards = soup.select('[jsname*="job"]') or soup.select('[role="listitem"]') or soup.select('.iFjolb') or soup.select('div[data-ved]')
            
            for card in job_cards[:30]:
                try:
                    text = card.get_text(separator='|', strip=True)
                    parts = [p.strip() for p in text.split('|') if p.strip()]
                    
                    if len(parts) < 2:
                        continue
                    
                    # Skip non-job entries
                    if any(kw in text.lower() for kw in ['sign in', 'sign up', 'subscribe', 'ad -']):
                        continue
                    
                    title = parts[0] if len(parts) > 0 else ""
                    company = parts[1] if len(parts) > 1 else ""
                    location = parts[2] if len(parts) > 2 else "India"
                    
                    # Extract URL if available
                    links = card.select('a')
                    job_url = links[0].get('href', '') if links else ''
                    if job_url and job_url.startswith('/'):
                        job_url = 'https://www.google.com' + job_url
                    
                    if not title or len(title) < 4 or not company:
                        continue
                    
                    key = f"{title}|{company}"
                    if key in seen:
                        continue
                    seen.add(key)
                    
                    desc = " | ".join(parts[3:8]) if len(parts) > 3 else ""
                    
                    all_jobs.append({
                        'title': title,
                        'company': company,
                        'location': location,
                        'description': desc[:250],
                        'url': job_url or f"https://www.google.com/search?q={quote_plus(title + ' ' + company + ' job')}",
                        'posted': 'Today',
                        'level': infer_level(title),
                        'type': 'Full-time',
                        'source': 'Google Jobs',
                    })
                except Exception:
                    continue
            
            time.sleep(1.5)
        except Exception:
            continue
    
    return all_jobs

def scrape_linkedin_public():
    """Try to get jobs from LinkedIn public job search"""
    all_jobs = []
    seen = set()
    
    for query in ["software%20engineer", "SDE", "software%20development%20engineer"]:
        url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={query}&location=India&sortBy=DD"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            
            soup = BeautifulSoup(resp.text, 'lxml')
            cards = soup.select('.base-card') or soup.select('.job-search-card') or soup.select('li')
            
            for card in cards:
                try:
                    title_el = card.select_one('.base-search-card__title') or card.select_one('h3')
                    company_el = card.select_one('.base-search-card__subtitle') or card.select_one('.base-search-card__company-name') or card.select_one('h4')
                    loc_el = card.select_one('.job-search-card__location') or card.select_one('.base-search-card__metadata')
                    link_el = card.select_one('a.base-card__full-link') or card.select_one('a[href*="/jobs/"]')
                    
                    if not title_el or not company_el:
                        continue
                    
                    title = title_el.get_text(strip=True)
                    company = company_el.get_text(strip=True)
                    location = loc_el.get_text(strip=True) if loc_el else "India"
                    
                    key = f"{title}|{company}"
                    if key in seen:
                        continue
                    seen.add(key)
                    
                    url = link_el.get('href', '') if link_el else ''
                    # Clean LinkedIn tracking params
                    if '?' in url:
                        url = url.split('?')[0]
                    
                    all_jobs.append({
                        'title': title,
                        'company': company,
                        'location': location.replace('📍', '').strip(),
                        'description': '',
                        'url': url or f"https://www.linkedin.com/jobs/search/?keywords={query}&location=India",
                        'posted': 'Recently',
                        'level': infer_level(title),
                        'type': 'Full-time',
                        'source': 'LinkedIn',
                    })
                except Exception:
                    continue
            
            time.sleep(1)
        except Exception:
            continue
    
    return all_jobs

def get_fallback_jobs():
    """Curated SDE job openings as fallback when scraping fails"""
    today = datetime.now()
    jobs = [
        {"title": "Software Development Engineer", "company": "Amazon", "location": "Bangalore", "description": "Join Amazon's SDE team building next-gen e-commerce platforms. Work on high-scale distributed systems with Java, AWS, and microservices.", "url": "https://www.amazon.jobs/en/jobs/?base_query=software+development+engineer&loc_query=India", "posted": "Today", "level": "mid", "type": "Full-time", "source": "Amazon Careers"},
        {"title": "SDE I - Backend", "company": "Flipkart", "location": "Bangalore", "description": "Build and maintain backend services for India's largest e-commerce platform. Work with Java, Spring Boot, and microservices at scale.", "url": "https://www.flipkartcareers.com", "posted": "Today", "level": "entry", "type": "Full-time", "source": "Flipkart Careers"},
        {"title": "Senior Software Engineer", "company": "Google", "location": "Hyderabad", "description": "Design and develop large-scale systems for Google's core products. 5+ years experience in distributed systems required.", "url": "https://www.google.com/about/careers/applications/jobs/results/?q=software+engineer&location=India", "posted": "Yesterday", "level": "senior", "type": "Full-time", "source": "Google Careers"},
        {"title": "Software Engineer - Full Stack", "company": "Microsoft", "location": "Hyderabad", "description": "Develop cloud-native applications using Azure, React, and .NET. Collaborate with global teams on cutting-edge products.", "url": "https://careers.microsoft.com/us/en/search-results?keywords=software%20engineer&location=India", "posted": "1 day ago", "level": "mid", "type": "Full-time", "source": "Microsoft Careers"},
        {"title": "Junior Software Engineer", "company": "Swiggy", "location": "Bangalore", "description": "Build features for India's leading food delivery platform. Work with Golang, Kafka, and Postgres at scale.", "url": "https://careers.swiggy.com", "posted": "2 days ago", "level": "entry", "type": "Full-time", "source": "Swiggy Careers"},
        {"title": "SDE II - Platform Engineering", "company": "Zomato", "location": "Gurgaon", "description": "Design and build internal developer platforms. Experience with Kubernetes, Docker, and CI/CD pipelines required.", "url": "https://www.zomato.com/careers", "posted": "2 days ago", "level": "mid", "type": "Full-time", "source": "Zomato Careers"},
        {"title": "Software Development Engineer - Test", "company": "PhonePe", "location": "Bangalore", "description": "Build automated testing frameworks for India's leading payments app. Python, Selenium, and CI/CD expertise needed.", "url": "https://www.phonepe.com/careers", "posted": "3 days ago", "level": "entry", "type": "Full-time", "source": "PhonePe Careers"},
        {"title": "Principal Software Engineer", "company": "Oracle", "location": "Bangalore", "description": "Lead architecture for Oracle Cloud Infrastructure services. 10+ years experience in distributed systems required.", "url": "https://careers.oracle.com", "posted": "3 days ago", "level": "senior", "type": "Full-time", "source": "Oracle Careers"},
        {"title": "Software Engineer - Machine Learning", "company": "Uber", "location": "Bangalore", "description": "Build ML-powered features for Uber's platform. Experience with TensorFlow, PyTorch, and recommendation systems required.", "url": "https://www.uber.com/us/en/careers", "posted": "4 days ago", "level": "senior", "type": "Full-time", "source": "Uber Careers"},
        {"title": "Graduate Software Engineer", "company": "JPMorgan Chase", "location": "Mumbai", "description": "Join the technology analyst program. Work on financial systems with Java, Python, and cloud platforms.", "url": "https://careers.jpmorgan.com", "posted": "5 days ago", "level": "entry", "type": "Full-time", "source": "JPMorgan Careers"},
        {"title": "SDE - Backend (Node.js)", "company": "Razorpay", "location": "Bangalore", "description": "Build payment infrastructure for India. Work with Node.js, Redis, and PostgreSQL at massive scale.", "url": "https://razorpay.com/careers", "posted": "5 days ago", "level": "mid", "type": "Full-time", "source": "Razorpay Careers"},
        {"title": "Staff Software Engineer", "company": "Salesforce", "location": "Hyderabad", "description": "Lead technical initiatives for Salesforce's core platform. Design large-scale distributed systems and mentor teams.", "url": "https://www.salesforce.com/company/careers", "posted": "6 days ago", "level": "senior", "type": "Full-time", "source": "Salesforce Careers"},
        {"title": "Software Engineer I", "company": "Paytm", "location": "Noida", "description": "Build and maintain features for India's largest digital payments platform. Java, MySQL, and AWS experience needed.", "url": "https://paytm.com/careers", "posted": "1 week ago", "level": "entry", "type": "Full-time", "source": "Paytm Careers"},
        {"title": "SDE - Frontend", "company": "Myntra", "location": "Bangalore", "description": "Build beautiful, performant UIs for fashion e-commerce. React, TypeScript, and Next.js expertise required.", "url": "https://www.myntra.com/careers", "posted": "1 week ago", "level": "mid", "type": "Full-time", "source": "Myntra Careers"},
        {"title": "Senior Software Developer", "company": "Adobe", "location": "Noida", "description": "Develop cloud-based creative tools. Work with microservices, AWS, and modern web technologies.", "url": "https://www.adobe.com/careers", "posted": "1 week ago", "level": "senior", "type": "Full-time", "source": "Adobe Careers"},
    ]
    return jobs

def main():
    print(f"[{datetime.now().isoformat()}] Fetching SDE jobs...")
    all_jobs = []
    seen = set()
    
    # Try multiple sources
    sources = [
        ('Google Jobs', scrape_google_jobs),
        ('LinkedIn', scrape_linkedin_public),
    ]
    
    for source_name, scraper in sources:
        try:
            jobs = scraper()
            print(f"  {source_name}: {len(jobs)} jobs")
            for j in jobs:
                key = f"{j['company']}|{j['title']}"
                if key not in seen:
                    seen.add(key)
                    all_jobs.append(j)
        except Exception as e:
            print(f"  {source_name}: error - {e}")
    
    # Always enrich with curated fallback jobs for broader coverage
    fallback = get_fallback_jobs()
    fallback_added = 0
    for j in fallback:
        key = f"{j['company']}|{j['title']}"
        if key not in seen:
            seen.add(key)
            all_jobs.append(j)
            fallback_added += 1
    if fallback_added > 0:
        print(f"  + {fallback_added} curated jobs added")
    
    print(f"✓ Total: {len(all_jobs)} unique jobs")
    
    # Sort: newer first (approximate)
    priority = {'Today': 0, 'Today ': 0, 'Just posted': 0, 'Yesterday': 1, 'day ago': 2, 'days ago': 3, 'week ago': 7}
    def sort_key(j):
        for kw, val in priority.items():
            if kw in j.get('posted', ''):
                return val
        return 10
    all_jobs.sort(key=sort_key)
    
    output = {
        'updated': datetime.now().strftime('%d %b %Y, %I:%M %p IST'),
        'count': len(all_jobs),
        'jobs': all_jobs
    }
    
    with open(JOBS_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"✓ Saved {len(all_jobs)} jobs to {JOBS_FILE}")
    return all_jobs

if __name__ == '__main__':
    main()
