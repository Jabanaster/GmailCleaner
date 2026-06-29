import dotenv
dotenv.load_dotenv()

from routes import create_app

asgi = create_app("./dist")

