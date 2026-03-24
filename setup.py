from setuptools import setup

APP = ["app.py"]
DATA_FILES = [
    ("assets", ["assets/bbc_news_theme.mp3", "assets/netflix.mp3", "assets/icon.png"]),
]
OPTIONS = {
    "argv_emulation": False,
    "iconfile": None,
    "plist": {
        "LSUIElement": True,
        "CFBundleName": "BBC Meet Jingle",
        "CFBundleIdentifier": "com.user.bbcmeetjingle",
        "CFBundleVersion": "1.0.0",
    },
    "packages": ["pygame", "googleapiclient", "google_auth_oauthlib", "pyobjc"],
    "includes": ["schedule"],
}

setup(
    name="BBC Meet Jingle",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
