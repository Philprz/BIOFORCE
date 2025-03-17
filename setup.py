from setuptools import setup, find_packages

setup(
    name="bioforce_scraper",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "uvicorn",
        "playwright",
        "qdrant-client",
        "openai",
        "apscheduler",
        "langdetect",
        "python-dotenv",
        "python-multipart",
        "beautifulsoup4",
        "httpx"
    ],
)
