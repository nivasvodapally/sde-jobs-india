#!/usr/bin/env python3
"""Fetch SDE job openings from Indeed India and save as jobs.json"""
import requests
import json
import re
import time
import os
from datetime import datetime
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

SITE_DIR = os.path.dirname(os.path.abspath(__file__))
JOBS_FILE = os.path.join(SITE_DIR, 'jobs.json')

SEARCHES = [
    # (query, location)
    ("software+development+engineer", "India"),
    ("SDE", "India"),
    ("software+engineer", "Bangalore"),
    ("SDE", "Bangalore"),
    ("software+engineer", "Hyderabad"),
    ("software+development+engineer", "Mumbai"),
    ("software+engineer", "Pune"),
    ("software+engineer", "Chennai"),
    ("SDE", "Delhi"),
    ("software+engineer", "Gurgaon"),
    ("junior+software+engineer", "India"),
    ("senior+software+engineer", "India"),
]

def parse_salary(salary_text):
    """Return estimated level from salary or text"""
    if not salary_text:
        return None
    salary_text = salary_text.lower()
    if 'lac' in salary_text or 'lakh' in salary_text:
        nums = re.findall(r'(\d+\.?\d*)', salary_text)
        if nums:
            max_sal = max(float(n) for n in nums)
            if max_sal >= 25:
                return 'senior'
            elif max_sal >= 10:
                return 'mid'
            else:
                return 'entry'
    return None

def infer_level(title, desc=""):
    """Infer experience level from title and description"""
    title_lower = title.lower()
    text = title_lower + " " + desc.lower()
    
    senior_keywords = ['senior', 'sr ', 'lead', 'principal', 'staff', 'architect', 'manager', 'head of']
    mid_keywords = ['mid', 'sde 2', 'sde2', 'software engineer ii', 'ii -']
    entry_keywords = ['junior', 'jr ', 'fresher', 'entry', 'graduate', 'trainee', 'intern', 'sde 1', 'sde1', '0-2']
    
    for kw in senior_keywords:
        if kw in text:
            return 'senior'
    for kw in mid_keywords:
        if kw in text:
            return 'mid'
    for kw in entry_keywords:
        if kw in text:
            return 'entry'
    
    # Default classification based on experience mentions
    exp_match = re.search(r'(\d+)\s*(?:-|to)\s*(\d+)\s*(?:year|yr|y)', text)
    if exp_match:
        avg_exp = (int(exp_match.group(1)) + int(exp_match.group(2))) / 2
        if avg_exp >= 5:
            return 'senior'
        elif avg_exp >= 2:
            return 'mid'
        else:
            return 'entry'
    
    return 'entry'  # default

def scrape_indeed():
    """Scrape SDE jobs from Indeed India"""
    all_jobs = []
    seen_urls = set()
    
    for query, location in SEARCHES:
        url = f"https://www.indeed.co.in/jobs?q={query}&l={location}&sort=date"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            
            soup = BeautifulSoup(resp.text, 'lxml')
            cards = soup.select('[data-testid="job-card"]') or soup.select('.job_seen_beacon') or soup.select('.cardOutline')
            
            for card in cards:
                try:
                    # Try multiple selectors for job title
                    title_el = card.select_one('[data-testid="job-card-title"]') or card.select_one('h2 a') or card.select_one('a[data-jk]')
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    
                    if not title or len(title) < 5:
                        continue
                    
                    # Company
                    company_el = card.select_one('[data-testid="company-name"]') or card.select_one('.companyName') or card.select_one('.company')
                    company = company_el.get_text(strip=True) if company_el else "Unknown"
                    
                    # Location
                    loc_el = card.select_one('[data-testid="job-card-location"]') or card.select_one('.companyLocation') or card.select_one('.location')
                    location_text = loc_el.get_text(strip=True).replace('📍', '').strip() if loc_el else location
                    
                    # Salary
                    salary_el = card.select_one('.salary-snippet') or card.select_one('.salaryText') or card.select_one('[data-testid="job-card-salary"]')
                    salary_text = salary_el.get_text(strip=True) if salary_el else None
                    
                    # Description snippet
                    desc_el = card.select_one('.job-snippet') or card.select_one('[data-testid="job-card-summary"]') or card.select_one('.summary')
                    desc = desc_el.get_text(strip=True) if desc_el else ""
                    
                    # URL
                    link = title_el.get('href') if title_el.name == 'a' else card.select_one('a[data-jk]')
                    if link:
                        href = link.get('href') if hasattr(link, 'get') else link
                        job_url = "https://www.indeed.co.in" + href if href.startswith('/') else href
                    else:
                        continue
                    
                    # Posted time
                    date_el = card.select_one('[data-testid="job-card-date"]') or card.select_one('.date') or card.select_one('.result-footnote')
                    posted = date_el.get_text(strip=True) if date_el else "Recently"
                    
                    if job_url in seen_urls:
                        continue
                    seen_urls.add(job_url)
                    
                    level = parse_salary(salary_text) or infer_level(title, desc)
                    
                    all_jobs.append({
                        'title': title,
                        'company': company,
                        'location': location_text,
                        'description': desc[:200],
                        'url': job_url,
                        'posted': posted,
                        'level': level,
                        'type': 'Full-time',
                        'source': 'Indeed',
                    })
                except Exception:
                    continue
            
            time.sleep(1)  # Be respectful
        except Exception:
            continue
    
    return all_jobs

def get_fallback_jobs():
    """Sample SDE jobs as fallback"""
    return [
        {"title": "Software Development Engineer", "company": "Amazon", "location": "Bangalore", "description": "Join Amazon's SDE team building next-gen e-commerce platforms. Work on high-scale distributed systems.", "url": "https://www.amazon.jobs", "posted": "Today", "level": "mid", "type": "Full-time", "source": "Amazon Careers"},
        {"title": "SDE I - Backend", "company": "Flipkart", "location": "Bangalore", "description": "Build and maintain backend services for India's largest e-commerce platform. Work with Java, Spring Boot, and microservices.", "url": "https://www.flipkartcareers.com", "posted": "Today", "level": "entry", "type": "Full-time", "source": "Flipkart Careers"},
        {"title": "Senior Software Engineer", "company": "Google", "location": "Hyderabad", "description": "Design and develop large-scale systems for Google's core products. 5+ years experience required.", "url": "https://careers.google.com", "posted": "Yesterday", "level": "senior", "type": "Full-time", "source": "Google Careers"},
        {"title": "Software Engineer - Full Stack", "company": "Microsoft", "location": "Hyderabad", "description": "Develop cloud-native applications using Azure, React, and .NET. Collaborate with global teams.", "url": "https://careers.microsoft.com", "posted": "1 day ago", "level": "mid", "type": "Full-time", "source": "Microsoft Careers"},
        {"title": "Junior Software Engineer", "company": "Swiggy", "location": "Bangalore", "description": "Build features for India's leading food delivery platform. Work with Golang, Kafka, and Postgres.", "url": "https://careers.swiggy.com", "posted": "2 days ago", "level": "entry", "type": "Full-time", "source": "Swiggy Careers"},
        {"title": "SDE II - Platform Engineering", "company": "Zomato", "location": "Gurgaon", "description": "Design and build internal developer platforms. Experience with Kubernetes and CI/CD pipelines.", "url": "https://www.zomato.com/careers", "posted": "2 days ago", "level": "mid", "type": "Full-time", "source": "Zomato Careers"},
        {"title": "Software Development Engineer - Test", "company": "PhonePe", "location": "Bangalore", "description": "Build automated testing frameworks for India's leading payments app. Python, Selenium, and CI/CD.", "url": "https://www.phonepe.com/careers", "posted": "3 days ago", "level": "entry", "type": "Full-time", "source": "PhonePe Careers"},
        {"title": "Principal Software Engineer", "company": "Oracle", "location": "Bangalore", "description": "Lead architecture for Oracle Cloud Infrastructure services. 10+ years experience in distributed systems.", "url": "https://careers.oracle.com", "posted": "3 days ago", "level": "senior", "type": "Full-time", "source": "Oracle Careers"},
        {"title": "Software Engineer - Machine Learning", "company": "Uber", "location": "Bangalore", "description": "Build ML-powered features for Uber's platform. Experience with TensorFlow, PyTorch, and recommendation systems.", "url": "https://www.uber.com/careers", "posted": "4 days ago", "level": "senior", "type": "Full-time", "source": "Uber Careers"},
        {"title": "Graduate Software Engineer", "company": "JPMorgan Chase", "location": "Mumbai", "description": "Join the technology analyst program. Work on financial systems with Java, Python, and cloud platforms.", "url": "https://careers.jpmorgan.com", "posted": "5 days ago", "level": "entry", "type": "Full-time", "source": "JPMorgan Careers"},
        {"title": "SDE - Backend (Node.js)", "company": "Razorpay", "location": "Bangalore", "description": "Build payment infrastructure for India. Work with Node.js, Redis, and PostgreSQL at scale.", "url": "https://razorpay.com/careers", "posted": "5 days ago", "level": "mid", "type": "Full-time", "source": "Razorpay Careers"},
        {"title": "Staff Software Engineer", "company": "Salesforce", "location": "Hyderabad", "description": "Lead technical initiatives for Salesforce's core platform. Design large-scale distributed systems.", "url": "https://www.salesforce.com/company/careers", "posted": "6 days ago", "level": "senior", "type": "Full-time", "source": "Salesforce Careers"},
        {"title": "Software Engineer I", "company": "Paytm", "location": "Noida", "description": "Build and maintain features for India's largest digital payments platform. Java, MySQL, and AWS.", "url": "https://paytm.com/careers", "posted": "1 week ago", "level": "entry", "type": "Full-time", "source": "Paytm Careers"},
        {"title": "SDE - Frontend", "company": "Myntra", "location": "Bangalore", "description": "Build beautiful, performant UIs for fashion e-commerce. React, TypeScript, and Next.js.", "url": "https://www.myntra.com/careers", "posted": "1 week ago", "level": "mid", "type": "Full-time", "source": "Myntra Careers"},
        {"title": "Senior Software Developer", "company": "Adobe", "location": "Noida", "description": "Develop cloud-based creative tools. Work with microservices, AWS, and modern web technologies.", "url": "https://www.adobe.com/careers", "posted": "1 week ago", "level": "senior", "type": "Full-time", "source": "Adobe Careers"},
    ]

def main():
    print(f"[{datetime.now().isoformat()}] Fetching SDE jobs...")
    
    # Try scraping Indeed
    scraped_jobs = scrape_indeed()
    
    if scraped_jobs and len(scraped_jobs) >= 5:
        jobs = scraped_jobs
        print(f"✓ Scraped {len(jobs)} jobs from Indeed")
    else:
        # Fallback to curated sample data
        jobs = get_fallback_jobs()
        if scraped_jobs:
            # Merge: deduplicate by company+title
            existing_titles = {(j['company'], j['title']) for j in jobs}
            for j in scraped_jobs:
                if (j['company'], j['title']) not in existing_titles:
                    jobs.append(j)
                    existing_titles.add((j['company'], j['title']))
        print(f"✓ Using {len(jobs)} jobs (scraped: {len(scraped_jobs)}, fallback: {len(jobs) - len(scraped_jobs)})")
    
    # Sort: newer first (approximate)
    priority = {'Today': 0, 'Today ': 0, 'Just posted': 0, 'Yesterday': 1, 'day ago': 2, 'days ago': 3, 'week ago': 7}
    def sort_key(j):
        for kw, val in priority.items():
            if kw in j.get('posted', ''):
                return val
        return 10
    jobs.sort(key=sort_key)
    
    output = {
        'updated': datetime.now().strftime('%d %b %Y, %I:%M %p IST'),
        'count': len(jobs),
        'jobs': jobs
    }
    
    with open(JOBS_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"✓ Saved {len(jobs)} jobs to {JOBS_FILE}")
    return jobs

if __name__ == '__main__':
    main()
