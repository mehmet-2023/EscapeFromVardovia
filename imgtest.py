import requests

def generate_image(prompt, width=512, height=512, seed=None):
    import urllib.parse
    encoded = urllib.parse.quote(prompt, safe='')
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}"
    if seed is not None:
        url += f"&seed={seed}"
    resp = requests.get(url)
    if resp.status_code == 200:
        with open("output.png", "wb") as f:
            f.write(resp.content)
        print("Image saved to output.png")
    else:
        print("Error:", resp.status_code, resp.text)

if __name__ == "__main__":
    generate_image("a broken neon-lit city street at night, cyberpunk, rainy, dramatic lighting")
