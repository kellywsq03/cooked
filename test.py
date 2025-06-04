from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv
import base64

load_dotenv("keys.env")
client = genai.Client()

contents = ("Generate an image for this recipe Recipe(title='Mango Sticky Rice', serving_size=4, prep_time=480, cook_time=20, ingredients='Sticky rice, coconut milk, sugar, salt, mangoes, sesame seeds', instructions='Rinse and soak sticky rice. Steam the rice. Make the coconut milk mixture. Combine rice and coconut milk. Make the thickened coconut sauce. Serve with mangoes and sesame seeds.', url='https://scientificallysweet.com/thai-mango-with-coconut-sticky-rice, https://theforkedspoon.com/mango-sticky-rice')")

response = client.models.generate_content(
    model="gemini-2.0-flash-preview-image-generation",
    contents=contents,
    config=types.GenerateContentConfig(
      response_modalities=['TEXT', 'IMAGE']
    )
)

for part in response.candidates[0].content.parts:
  if part.text is not None:
    print(part.text)
  elif part.inline_data is not None:
    img_data = base64.b64decode(part.inline_data.data)
    image = Image.open(BytesIO((img_data)))
    image.save('gemini-native-image.png')
    image.show()