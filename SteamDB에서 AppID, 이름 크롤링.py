from bs4 import BeautifulSoup

url = "https://steamdb.info/tag/492/?category=-888&cc=us&displayOnly=Game&min_price=1&sort=followers_desc"


soup = BeautifulSoup(html_content, "html.parser")