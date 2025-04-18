import os
import chainlit as cl
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import requests
import json
from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain
import pdfplumber

# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# Initialize Language Model
llm = ChatOpenAI(
    model_name="gpt-4",
    temperature=0.7,
    openai_api_key=openai_api_key
)

cover_letter_template = """
 You are an expert career coach. Write a professional and personalized cover letter using the following information:
 
 Job Description:
 {job_description}
 
 Candidate's Resume:
 {cv_text}
 
 
 Please make sure the cover letter:
 1. Matches what the job requires (use specific examples from the CV)
 2. Shows off the candidate's best skills and achievements
 3. Sounds professional but friendly
 4. Fits on one page
 5. Has a strong beginning and ending
 6. Shows understanding of what the company needs
 
 Write the cover letter below:
 """

cover_letter_prompt = ChatPromptTemplate.from_template(cover_letter_template)

# Create a chain for the cover letter execution
cover_letter_chain = LLMChain(
    llm=llm, prompt=cover_letter_prompt, output_key="cover_letter")

# Helper functions


def check_job_description(text):
    """
     Check if the job description looks valid.
     Returns: (is_valid, message)
     """

    # If it is too short, do not proceed with the generation
    if len(text.split()) < 20:
        return False, "⚠️ The job description seems too short. We need more details to make a good cover letter!"

    return True, "✅ Job description looks good!"


def read_file_content(file_path):
    """
     Read text from a PDF or Word document.
     Returns: (extracted_text, message)
     """
    try:
        text = ""
        # For PDF files
        if file_path.endswith(".pdf"):
            with pdfplumber.open(file_path) as pdf:
                # Get text from each page
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"

        else:
            return None, "❌ Sorry! We only accept PDF or Word (.docx) files."

        # Check if we got any text
        if not text.strip():
            return None, "❌ Couldn't read any text from your file."

        # Check if the CV is too short
        if len(text.split()) < 50:
            return None, "❌ The CV seems to be too short."

        return text, "✅ Successfully read your CV!"

    except Exception as e:
        return None, f"❌ Oops! There was a problem reading your file: {str(e)}"


async def create_cover_letter(job_description, cv_text):
    """
     Generate a cover letter using our OpenAI
     Returns: (cover_letter, message)
     """
    try:
        # Ask the AI to generate the cover letter
        result = cover_letter_chain.invoke({
            "job_description": job_description,
            "cv_text": cv_text,
        })

        return result['cover_letter'], "Cover letter generated successfully!"

    except Exception as e:
        return None, f"Something went wrong: {str(e)}"


@cl.on_chat_start
async def welcome():
    """Show welcome message when someone starts the chat"""

    # Main welcome message
    await cl.Message(content="# 👋 Welcome to the Cover Letter Generator! 📝").send()

    # Second welcome message
    await cl.Message(content="Please provide me with the following information:").send()
    await cl.Message(content="1. Job Description").send()


@cl.on_message
async def main(message: cl.Message):
    # Get the current state of our conversation
    chat_history = cl.user_session.get('history', {})
    current_step = chat_history.get('state', 'job_description')

    # Step 1: Handle Job Description
    if current_step == 'job_description':
        status_msg = cl.Message(content="Processing job description...")
        await status_msg.send()

        # Check if the job description looks valid
        is_valid, feedback = check_job_description(message.content)
        if not is_valid:
            await cl.Message(content=feedback).send()
            return

        # Save the job description and move to next step
        chat_history['job_description'] = message.content
        chat_history['state'] = 'cv_upload'
        cl.user_session.set('history', chat_history)

        await cl.Message(content="Job description processed successfully!").send()

        # Immediately ask for file upload instead of waiting for another message
        files = await cl.AskFileMessage(
            content="### Please upload your CV/Resume as a PDF",
            accept=["application/pdf"]
        ).send()

        # Process the uploaded file
        cv_text, file_message = read_file_content(files[0].path)
        if cv_text is None:
            await cl.Message(content=file_message).send()
            return

        status_msg = cl.Message(content="Generating your cover letter...")
        await status_msg.send()

        # Generate the cover letter
        cover_letter, gen_message = await create_cover_letter(
            chat_history['job_description'],
            cv_text
        )

        if cover_letter is None:
            await cl.Message(content=gen_message).send()
            return

        # Save everything and move to feedback step
        chat_history['cv_text'] = cv_text
        chat_history['current_cover_letter'] = cover_letter
        chat_history['state'] = 'feedback'
        cl.user_session.set('history', chat_history)

        # Show the cover letter and ask for feedback
        await cl.Message(content="**Here is your cover letter").send()
        await cl.Message(content=cover_letter).send()
