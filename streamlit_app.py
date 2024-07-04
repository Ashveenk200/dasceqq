import streamlit as st
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import mysql.connector
from datetime import datetime

# MySQL connection setup
def init_connection():
    return mysql.connector.connect(
        host="sql12.freesqldatabase.com",
        user="sql12717887",
        password="RYIGenrwdP",  # replace with your actual MySQL password
        database="sql12717887",
        port=3306
    )

# Function to insert a new conversation into the database
def insert_conversation(conn, user_id, name, user_question, bot_answer, time):
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO botssdata (user_id, name, userquestion, botanswer, time) VALUES (%s, %s, %s, %s, %s)",
        (user_id, name, user_question, bot_answer, time)
    )
    conn.commit()
    cursor.close()

# Function to insert a new user into the database
def insert_user(conn, user_id, name):
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (user_id, name) VALUES (%s, %s)",
        (user_id, name)
    )
    conn.commit()
    cursor.close()

# Predefined SQL queries for payment-related calculations
def predefined_query(query, user_id):
    conn = init_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, (user_id,))
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return result

# Streamlit app title
st.title("Dasceq Chatbot")

# Custom CSS for chat messages
st.markdown("""
<style>
.chat-message {
    border-radius: 10px;
    padding: 10px;
    margin: 10px;
    display: inline-block;
    max-width: 70%;
}
.user-message {
    color: black;
    background-color: #dcf8c6;
    align-self: flex-end;
}
.bot-message {
    color: black;
    background-color: #ececec;
    align-self: flex-start;
}
.chat-container {
  display: flex;
  flex-direction: column-reverse;  
  height: 4px;
  overflow-y: scroll;
}
</style>
""", unsafe_allow_html=True)

# Initialize Hugging Face tokenizer and model for DialoGPT
tokenizer = AutoTokenizer.from_pretrained("microsoft/DialoGPT-medium")
model = AutoModelForCausalLM.from_pretrained("microsoft/DialoGPT-medium")

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'name' not in st.session_state:
    st.session_state.name = None
if 'start_time' not in st.session_state:
    st.session_state.start_time = None
if 'chat_history_ids' not in st.session_state:
    st.session_state.chat_history_ids = None
if 'selected_table' not in st.session_state:
    st.session_state.selected_table = None

# Connect to the database
conn = init_connection()

# User input form for name and ID
if st.session_state.user_id is None:
    with st.form(key='user_form'):
        user_id = st.text_input("Enter your ID:")
        name = st.text_input("Enter your name:")
        submit_user = st.form_submit_button("Submit")

        if submit_user and user_id and name:
            st.session_state.user_id = user_id
            st.session_state.name = name
            st.session_state.start_time = datetime.now()
            insert_user(conn, user_id, name)
            st.success(f"Hi {name}, you can now ask your questions.")

# Function to generate response
def generate_response(user_message):
    st.session_state.messages.append({"role": "user", "content": user_message})

    # Encode conversation history
    new_user_input_ids = tokenizer.encode(user_message + tokenizer.eos_token, return_tensors='pt')

    # Append the new user input tokens to the chat history
    if len(st.session_state.messages) == 1:
        bot_input_ids = new_user_input_ids
    else:
        if st.session_state.chat_history_ids is not None:
            bot_input_ids = torch.cat([st.session_state.chat_history_ids, new_user_input_ids], dim=-1)
        else:
            bot_input_ids = new_user_input_ids

    # Generate a response
    chat_history_ids = model.generate(bot_input_ids, max_length=1000, pad_token_id=tokenizer.eos_token_id)

    # Decode the response
    bot_message = tokenizer.decode(chat_history_ids[:, bot_input_ids.shape[-1]:][0], skip_special_tokens=True)

    # Check if the response contains keywords indicating an unsuccessful answer
    if any(word in bot_message.lower() for word in ["sorry", "can't", "not"]):
        bot_message = handle_fallback(user_message)

    st.session_state.messages.append({"role": "assistant", "content": bot_message})

    # Update the chat history
    st.session_state.chat_history_ids = chat_history_ids

    # Store the message and response in the database
    end_time = datetime.now()
    insert_conversation(conn, st.session_state.user_id, st.session_state.name, user_message, bot_message, end_time)

# Fallback to SQL queries if the bot response is not satisfactory
def handle_fallback(user_message):
    user_id = st.session_state.user_id
    table = "payments"  # Specify the table to be used

    # Identify the keyword in the user message
    keywords = {
        "max": "SELECT MAX(amount) as result FROM {} WHERE user_id = %s",
        "min": "SELECT MIN(amount) as result FROM {} WHERE user_id = %s",
        "average": "SELECT AVG(amount) as result FROM {} WHERE user_id = %s",
        "count": "SELECT COUNT(*) as result FROM {} WHERE user_id = %s",
        "sum": "SELECT SUM(amount) as result FROM {} WHERE user_id = %s"
    }

    for keyword, query_template in keywords.items():
        if keyword in user_message.lower():
            query = query_template.format(table)
            result = predefined_query(query, user_id)
            if result:
                return f"The {keyword} amount is {result[0]['result']}."
    
    # If no keyword is matched, ask user to clarify
    return "Could you please clarify your request or provide more details?"

# Create a form for user input
if st.session_state.name is not None:
    with st.form(key='chat_form', clear_on_submit=True):
        input_message = st.text_input(f"{st.session_state.name}:", key="input_message")
        submit_button = st.form_submit_button("Send")

        # If form is submitted, handle the message
        if submit_button and input_message:
            generate_response(input_message)

    # Display conversation history
    st.markdown("<div class='chat-container'>", unsafe_allow_html=True)
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.markdown(f"<div class='chat-message user-message'><strong>You:</strong> {message['content']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='chat-message bot-message'><strong>Dasceq:</strong> {message['content']}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# Close database connection
conn.close()
