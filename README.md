# Nemotron Chat

## Local run
1. Install Python 3.10+.
2. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.
3. Put your **newly rotated** NVIDIA API key in `.streamlit/secrets.toml`.
4. Run `pip install -r requirements.txt`
5. Run `streamlit run app.py`

## Deploy to Streamlit Community Cloud
1. Push `app.py`, `requirements.txt`, `.gitignore`, and this README to a GitHub repository.
2. Do NOT commit `.streamlit/secrets.toml`; it is ignored by Git.
3. Create an app at https://share.streamlit.io/ and select the repository and `app.py`.
4. In the app's Advanced settings / Secrets, enter:
   ```toml
   NVIDIA_API_KEY = "your_new_rotated_key"
   NVIDIA_MODEL_ID = "nvidia/nemotron-3-ultra-550b-a55b"
   ```
5. Deploy and use the URL Streamlit provides.

## Notes
- The API key is server-side and is not shown in the app UI.
- Add authentication or other access control before sharing the URL publicly; visitors can otherwise consume your API quota.
- Chat/project state is held in Streamlit session state. It is not a durable multi-user database; add a database/authentication layer if persistent cross-device history is required.
- Thinking display depends on model/API support.
