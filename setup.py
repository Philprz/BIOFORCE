from setuptools import setup, find_packages

setup(
    name="bioforce-scraper",
    version="1.0.0",
    description="Bioforce Scraper et Chatbot",
    author="Bioforce",
    author_email="contact@bioforce.org",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "fastapi>=0.95.0",
        "uvicorn>=0.21.1",
        "pydantic>=1.10.7",
        "aiohttp>=3.8.4",
        "beautifulsoup4>=4.12.0",
        "playwright>=1.32.1",
        "openai>=0.27.4",
        "qdrant-client>=1.1.1",
        "python-dotenv>=1.0.0",
        "jinja2>=3.1.2",
        "apscheduler>=3.10.1",
        "numpy>=1.24.3",
        "requests>=2.28.2",
    ],
    entry_points={
        "console_scripts": [
            "bioforce-scraper=launch:main",
        ],
    },
    python_requires=">=3.8",
)
