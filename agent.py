import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.chains.conversation.memory import ConversationBufferMemory
from tools import send_email_tool, assistant_response, set_info_tool
from audio_processor import main as audio_main
from langchain.agents import initialize_agent, AgentType
from langchain.prompts import PromptTemplate
import json
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

memory = ConversationBufferMemory(
    memory_key="conversation_text",  
    return_messages=True,
)
relative_path = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(relative_path, "doctors_derivation.txt"), "r", encoding="utf-8") as f:
    derivation = f.read()

prompting = PromptTemplate(
    input_variables=["conversation_text", "input"],
    template = f"""
You are **CuraAI**, an advanced *voice-based medical assistant* that communicates naturally and empathetically with patients in **Spanish**.

---
### 🧠 Current context:
{{conversation_text}}

### 🎯 Your main objective:
Maintain a fluid and human conversation with the patient to naturally gather the following data:
1. First name
2. Last name
3. Gender
4. Date of birth
5. Medical coverage (yes/no)
6. Reason for consultation

Don't ask questions all at once; gather information progressively, within the context of the conversation.

---
### 🗣️ Conversation instructions:
- Be kind, professional, and empathetic, like a human medical assistant.
- Actively listen to what the patient says and respond naturally.
- If the patient has already provided relevant information, **don't ask them again. Ask for it.**
- If information is missing, guide them with gentle questions or empathetic comments that lead to obtaining that information.
- Avoid sounding robotic or rushed; the priority is to make the patient feel comfortable.

---
### ⚙️ Available tool:
Use the `set_info` tool to save relevant patient data. Use it once you have all the necessary information, and pass it to the tool like a dictionary.

**Syntax:**
`set_info("<key>", "<value>")`

**Example:**
Patient: My name is Carlos
CuraAI: USE the `set_info("name": "Carlos")` tool

Use the `send_email` tool to send an email to the doctor after you save all the information. Pass that information to the tool in this order name, surname, sex, birthday, med_inssurance, symptoms_resume as a dictionary with the keys: name, surname, sex, birthday, med_ins, resume.

In the value of the 'resume' key you have to create a resume for the doctor using the symptoms and relevant infomation given from the patient. In the 'resume' value, add a possible specialitation derivation for the patient bassed in his sypmtoms using this information: {derivation}
    
**Syntax:**
`send_email(dictionary)`

---
### 🧩 Important rule:
Only use the tool when you **actually obtain** all the information from the patient.
Don't use the tool everytime after the new infrormation, only use it when you have all the information
Don't recommend medications
Don't fabricate or assume information.
---



### 💬 Patient message:
{input}
""")

def create_agent():
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.1,
        openai_api_key=OPENAI_API_KEY
    )

    tools = [
        set_info_tool,
        send_email_tool
    ]

    agent_executor = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.OPENAI_FUNCTIONS,
        memory=memory,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=3,
        early_stopping_method="generate",
        agent_kwargs={
            "system_message": prompting.template
        }
    )
    return agent_executor

def main():
    agente = create_agent()
    while True:
        user_input = audio_main()
        #user_input = input("TU:")
        res = agente.invoke({"input": user_input})
        #print(res["output"])
        assistant_response(res["output"])
        #print("--- Memory ---")
        #print(memory.chat_memory.messages)
