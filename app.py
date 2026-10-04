import json
import asyncio

import streamlit as st

from google import genai
from google.genai import types

from telegram import Bot

from prompts import (
    SUMMARY_REQUEST_PROMPT,
    SYSTEM_PROMPT,
    WELCOME_MESSAGE_TEMPLATE,
)


MODEL_NAME = "gemini-3.5-flash"

st.set_page_config(
    page_title="Deadline Tracker",
    page_icon="📅"
)


GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
TELEGRAM_BOT_TOKEN = st.secrets["TELEGRAM_BOT_TOKEN"]


@st.cache_resource
def get_gemini_client():

    return genai.Client(api_key=GEMINI_API_KEY)


@st.cache_resource
def get_telegram_client():

    return Bot(token=TELEGRAM_BOT_TOKEN)


gemini_client = get_gemini_client()
telegram_client = get_telegram_client()


def render_message(message):

    with st.chat_message(message["role"]):

        if message["kind"] == "text":

            st.write(message["content"])

        elif message["kind"] == "image":

            st.image(message["content"])

        elif message["kind"] == "file":

            st.write(message["content"])


def add_message(role, kind, content):

    st.session_state.messages.append(
        {
            "role": role,
            "kind": kind,
            "content": content,
        }
    )

    render_message(
        st.session_state.messages[-1]
    )


def ask_gemini(parts):

    try:

        return st.session_state.chat.send_message(parts).text

    except Exception as error:

        return f"Sorry, something went wrong: {error}"


def send_telegram(to_chat_id, summary):

    try:

        async def send_message():

            await telegram_client.send_message(
                chat_id=int(to_chat_id),
                text=summary,
            )

        asyncio.run(send_message())

        return True, "Message sent successfully."

    except Exception as error:

        return False, str(error)


# Step 1: onboarding

if "onboarded" not in st.session_state:

    st.title("📅 Deadline Tracker")

    st.caption(
        "Upload it. Track it. Never miss a deadline."
    )

    with st.form("onboarding_form"):

        name = st.text_input(
            "Your name"
        )

        telegram_chat_id = st.text_input(
            "Telegram Chat ID",
            placeholder="123456789",
        )

        submitted = st.form_submit_button(
            "Let's go 🚀"
        )

    if submitted:

        if (
            not name.strip()
            or not telegram_chat_id.strip()
        ):

            st.warning(
                "Please fill in both your name "
                "and Telegram Chat ID."
            )

        else:

            st.session_state.name = name.strip()

            st.session_state.telegram_chat_id = (
                telegram_chat_id.strip()
            )

            st.session_state.chat = (
                gemini_client.chats.create(
                    model=MODEL_NAME,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT
                    ),
                )
            )

            st.session_state.messages = []

            st.session_state.onboarded = True

            st.rerun()

    st.stop()


# Step 2: deadline tracker interface

header_col, button_col = st.columns(
    [5, 2],
    vertical_alignment="center",
)


with header_col:

    st.title("📅 Deadline Tracker")


with button_col:

    send_disabled = (
        len(st.session_state.messages) <= 1
    )

    if st.button(
        "📤 Send to Telegram",
        disabled=send_disabled,
        use_container_width=True,
    ):

        with st.spinner(
            "Summarizing your deadlines..."
        ):

            summary = ask_gemini(
                [SUMMARY_REQUEST_PROMPT]
            )

        success, info = send_telegram(
            st.session_state.telegram_chat_id,
            summary,
        )

        if success:

            st.success(
                "Sent! Check your Telegram 📲"
            )

        else:

            st.error(
                f"Couldn't send that: {info}"
            )

            st.write(
                "Chat ID being used:",
                st.session_state.telegram_chat_id,
            )


st.caption(
    f"Logged in as {st.session_state.name} - "
    f"updates go to Telegram"
)


if not st.session_state.messages:

    add_message(
        "assistant",
        "text",
        WELCOME_MESSAGE_TEMPLATE.format(
            name=st.session_state.name
        ),
    )

else:

    for message in st.session_state.messages:

        render_message(message)


# Step 3: handling input: documents and photos

user_input = st.chat_input(
    "Ask a question, or attach a syllabus/document",
    accept_file=True,
    file_type=[
        "jpg",
        "jpeg",
        "png",
        "pdf",
    ],
)


if user_input:

    uploaded_file = (
        user_input.files[0]
        if user_input.files
        else None
    )

    text = user_input.text

    parts = []


    if uploaded_file is not None:

        file_bytes = uploaded_file.getvalue()

        if uploaded_file.type.startswith("image/"):

            add_message(
                "user",
                "image",
                file_bytes,
            )

        else:

            add_message(
                "user",
                "file",
                uploaded_file.name,
            )

        parts.append(
            types.Part.from_bytes(
                data=file_bytes,
                mime_type=uploaded_file.type,
            )
        )


    if text:

        add_message(
            "user",
            "text",
            text,
        )

        parts.append(text)

    elif uploaded_file is not None:

        parts.append(
            "Extract all important deadlines, "
            "dates, examinations, assignments, "
            "submissions, registrations, and "
            "academic events from this document."
        )


    with st.spinner(
        "Finding your deadlines..."
    ):

        answer = ask_gemini(parts)


    add_message(
        "assistant",
        "text",
        answer,
    )