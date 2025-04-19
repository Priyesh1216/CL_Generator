import os
import chainlit as cl
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain
import pdfplumber
import docx2txt

# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# Initialize Language Model
llm = ChatOpenAI(
    model_name="gpt-3.5-turbo",
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


async def revise_cover_letter(job_description, cv_text, current_cover_letter, feedback):
    """
    Generate a revised cover letter based on user feedback
    Returns: (revised_cover_letter, message)
    """
    revision_template = """
    You are an expert career coach. Revise the cover letter based on the user's specific feedback.
    
    Job Description:
    {job_description}
    
    Candidate's Resume:
    {cv_text}
    
    Current Cover Letter:
    {current_cover_letter}
    
    User's Feedback:
    {feedback}
    
    IMPORTANT INSTRUCTIONS:
    1. DO NOT rewrite the entire cover letter. Start with the current cover letter as your base.
    2. ONLY modify the specific parts mentioned in the user's feedback.
    3. Preserve all other content, tone, and structure from the original cover letter.
    4. Make targeted changes that directly address the user's specific requests.
    5. If the user requests contradicts the resume, prioritize the user's feedback over CV content.
    6. Maintain the professional tone and appropriate length.
    
    Write the revised cover letter below:
    """

    revision_prompt = ChatPromptTemplate.from_template(revision_template)

    revision_chain = LLMChain(
        llm=llm, prompt=revision_prompt, output_key="revised_cover_letter")

    try:
        # Ask the AI to revise the cover letter
        result = revision_chain.invoke({
            "job_description": job_description,
            "cv_text": cv_text,
            "current_cover_letter": current_cover_letter,
            "feedback": feedback
        })

        return result['revised_cover_letter'], "Cover letter revised successfully!"

    except Exception as e:
        return current_cover_letter, f"Error revising cover letter: {str(e)}"


# Helper functions


def check_job_description(text):
    """
     Check if the job description looks valid.
     Returns: (is_valid, message)
     """

    # If it is too short, do not proceed with the generation
    if len(text.split()) < 20:
        return False, "The job description is too short. Provide more details."

    return True, "It is good"


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

        # For Word documents
        elif file_path.endswith(".docx"):
            # Use docx2txt to extract text from Word document
            text = docx2txt.process(file_path)

        else:
            return None, "Only PDF files are supported. Please upload PDF files."

        # Check if we got any text
        if not text.strip():
            return None, "Couldn't read any text from your file."

        # Check if the CV is too short
        if len(text.split()) < 50:
            return None, "The CV is too short."

        return text, "Successfully read your CV!"

    except Exception as e:
        return None, f"Oops! There was a problem reading your file: {str(e)}"


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
    await cl.Message(content="#Welcome to the Cover Letter Generator!").send()

    # Second welcome message
    await cl.Message(content="Please provide me with the the job description (text):").send()


@cl.on_message
async def main(message: cl.Message):
    # Get the current state of conversation
    chat_history = cl.user_session.get('history', {})
    current_step = chat_history.get('state', 'job_description')

    # Step 1: Handle Job Description
    if current_step == 'job_description':
        status_msg = cl.Message(content="Processing job description...")
        await status_msg.send()

        # Check if the job description looks valid
        # check_job_description returns: boolean, string
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
            content="### Please upload your CV/Resume as a PDF or docx",
            accept=["application/pdf",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
        ).send()

        # Process the uploaded file
        cv_text, file_message = read_file_content(files[0].path)
        if cv_text is None:
            await cl.Message(content=file_message).send()
            return

        status_msg = cl.Message(content="Generating your cover letter...")
        await status_msg.send()

        # Generate the cover letter
        cover_letter, generation_message = await create_cover_letter(
            chat_history['job_description'],
            cv_text
        )

        if cover_letter is None:
            await cl.Message(content=generation_message).send()
            return

        # Save and move to feedback step
        chat_history['cv_text'] = cv_text
        chat_history['current_cover_letter'] = cover_letter
        chat_history['feedback_count'] = 0
        cl.user_session.set('history', chat_history)

        # Show the cover letter
        await cl.Message(content="**Here is your cover letter**").send()
        await cl.Message(content=cover_letter).send()

        # Ask the user if they are satisfied
        try:
            is_satisfied = await cl.AskActionMessage(
                content="Are you satisfied with the cover letter?",
                actions=[
                    cl.Action(name="Yes",
                              payload={"value": "yes"},
                              label="Yes",
                              tooltip="Yes, I'm satisfied with the cover letter"),

                    cl.Action(name="No",
                              payload={"value": "no"},
                              label="No",
                              tooltip="No, I'm not satisfied with the cover letter")
                ]).send()

            # Process action result immediately
            if is_satisfied.get("value") == "yes":
                await cl.Message(content="Your cover letter is ready to use! Good luck on your application.").send()
                chat_history['state'] = 'completed'
                cl.user_session.set('history', chat_history)
            else:
                # Handle "No" response immediately
                feedback_count = chat_history.get('feedback_count', 0)
                remaining = 5 - feedback_count

                # Ask for specific feedback right away
                await cl.Message(content=f"Please provide specific feedback on what you'd like to change. You have {remaining} revision(s) remaining.").send()

                # Set state for next message
                chat_history['state'] = 'waiting_for_feedback'
                cl.user_session.set('history', chat_history)

        except Exception as e:
            await cl.Message(content=f"ERROR: {str(e)}").send()

    # Handle user feedback for revisions
    elif current_step == 'waiting_for_feedback':
        # User has provided feedback, generate a new cover letter
        status_msg = cl.Message(
            content="Revising your cover letter based on your feedback...")
        await status_msg.send()

        # Get the feedback count
        feedback_count = chat_history.get('feedback_count', 0)

        # Generate a revised cover letter
        revised_cover_letter, _ = await revise_cover_letter(
            chat_history['job_description'],
            chat_history['cv_text'],
            chat_history['current_cover_letter'],
            message.content  # This is the user's feedback
        )

        # Update chat history
        chat_history['current_cover_letter'] = revised_cover_letter
        chat_history['feedback_count'] += 1

        # Update local variable
        feedback_count = chat_history['feedback_count']
        cl.user_session.set('history', chat_history)

        # Show the revised cover letter
        await cl.Message(content=f"**Here is revision #{feedback_count} of your cover letter**").send()
        await cl.Message(content=revised_cover_letter).send()

        # Check if max revisions reached
        if feedback_count >= 5:
            await cl.Message(content="You've reached the maximum number of revisions (5). This is your final cover letter.").send()
            chat_history['state'] = 'completed'
            cl.user_session.set('history', chat_history)
            return

        # Ask for feedback again with buttons
        try:
            is_satisfied = await cl.AskActionMessage(
                content="Are you satisfied with the revised cover letter?",
                actions=[
                    cl.Action(name="Yes",
                              payload={"value": "yes"},
                              label="Yes",
                              tooltip="Yes, I'm satisfied with the cover letter"),

                    cl.Action(name="No",
                              payload={"value": "no"},
                              label="No",
                              tooltip="No, I'm not satisfied with the cover letter")
                ]).send()

            # Process action result immediately
            if is_satisfied.get("value") == "yes":
                await cl.Message(content="Your cover letter is ready to use! Good luck on your application.").send()
                chat_history['state'] = 'completed'
                cl.user_session.set('history', chat_history)
            else:
                # Handle "No" response immediately
                remaining = 5 - feedback_count
                await cl.Message(content=f"Please provide specific feedback on what you'd like to change. You have {remaining} revision(s) remaining.").send()

                # Set state for next message
                chat_history['state'] = 'waiting_for_feedback'
                cl.user_session.set('history', chat_history)

        except Exception as e:
            await cl.Message(content=f"ERROR: {str(e)}").send()
