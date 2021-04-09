import urllib.parse

def login(user, pw, client, host):
    oldhost = host
    parsed = urllib.parse.urlparse(host)
    subdomain, domain = parsed.netloc.split('.', maxsplit=1)
    # Replace subdomain - logins should be on www.
    host = f'{parsed.scheme}://www.{domain}'
    location = '/accounts/login/'
    URL = f'{host}{location}'

    # Go to login page at www. address
    client.get(URL)
    csrftoken = client.cookies['csrftoken']
    # Then login
    client.post(URL, data={'login': user, 'password': pw, 'csrfmiddlewaretoken': csrftoken},)

