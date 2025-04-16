# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.common.by import By
# from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# import time
# import re
# import asyncio
# import threading
# import os
# from dotenv import load_dotenv
# from llm_api import LLMClient
# from animations import animated_thinking

# # Load environment variables from .env file
# load_dotenv()

# # Environment for development/testing
# ENVIRONMENT = os.getenv('ENVIRONMENT', 'test') 

# # Create LLM client
# llm_client = LLMClient()

# class WhatsAppBot:
#     def __init__(self):
#         """
#         Initialize the WhatsApp bot with Selenium
#         """
#         print("Initializing WhatsApp Bot...")
        
#         # Set up Chrome options
#         chrome_options = Options()
#         chrome_options.add_argument("--start-maximized")
        
#         # Uncomment the following line to run in headless mode (no visible browser window)
#         # chrome_options.add_argument("--headless")
        
#         chrome_options.add_argument("--disable-notifications")
#         chrome_options.add_argument("--disable-popup-blocking")
#         chrome_options.add_argument("--disable-extensions")
#         chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
        
#         # Add service object for Chrome WebDriver
#         service = Service()
        
#         # Initialize the WebDriver
#         self.driver = webdriver.Chrome(service=service, options=chrome_options)
#         self.wait = WebDriverWait(self.driver, 30)
        
#         # Open WhatsApp Web
#         self.driver.get("https://web.whatsapp.com/")
#         print("Please scan the QR code to login to WhatsApp Web")
        
#         # Wait for QR code scan and login
#         try:
#             self.wait.until(EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true']")))
#             print("Successfully logged in!")
#         except Exception as e:
#             print(f"Failed to log in: {str(e)}")
#             self.driver.quit()
#             raise Exception("Login failed. Please try again.")
    
#     def listen_for_messages(self):
#         """
#         Start listening for incoming messages
#         """
#         print("Listening for messages...")
        
#         # Use a separate thread for the message processing loop
#         thread = threading.Thread(target=self._message_loop)
#         thread.daemon = True
#         thread.start()
        
#         # Keep the main thread alive
#         try:
#             while True:
#                 time.sleep(1)
#         except KeyboardInterrupt:
#             print("Bot stopped by user")
#             self.driver.quit()
    
#     def _message_loop(self):
#         """
#         Internal method to continuously check for new messages
#         """
#         last_processed_message = {}
        
#         while True:
#             try:
#                 # Look for unread messages (those with the unread message indicator)
#                 unread_chats = self.driver.find_elements(By.XPATH, "//span[@data-testid='icon-unread']")
                
#                 if unread_chats:
#                     # Click the first unread chat
#                     unread_chats[0].click()
#                     time.sleep(1)
                    
#                     # Get the chat name
#                     chat_name = self.driver.find_element(By.XPATH, "//div[@data-testid='conversation-info-header']").text
                    
#                     # Get the last message in the chat
#                     messages = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'message-in')]")
#                     if messages:
#                         last_message = messages[-1]
#                         message_text = last_message.text
                        
#                         # Check if this is a new message (not already processed)
#                         message_id = f"{chat_name}:{message_text}"
#                         if message_id not in last_processed_message:
#                             last_processed_message[message_id] = True
                            
#                             # Process the message if it starts with a command
#                             if message_text.startswith('/gpt '):
#                                 prompt = message_text[5:].strip()  # Remove '/gpt ' prefix
#                                 self._handle_gpt_command(prompt)
#             except Exception as e:
#                 print(f"Error in message loop: {str(e)}")
            
#             # Sleep before checking for new messages again
#             time.sleep(2)
    
#     def _handle_gpt_command(self, prompt):
#         """
#         Handle the /gpt command by calling the GitHub API
        
#         Args:
#             prompt (str): The prompt to send to the API
#         """
#         print(f"Handling /gpt command with prompt: {prompt}")
        
#         # Send initial "thinking" message
#         self._send_message("Thinking... I'll respond shortly.")
        
#         # Create a system message for GitHub model
#         system_prompt = "You are a helpful AI assistant."
        
#         try:
#             # Check if in test mode
#             if llm_client.environment.lower() == 'test':
#                 # In test mode, use a test response
#                 response = "This is a test response. In test mode, we simulate model responses with this message."
#             else:
#                 # Call the GitHub model
#                 response = llm_client.call_github(system_prompt, prompt)
            
#             # Send the response
#             self._send_message(response)
#         except Exception as e:
#             error_msg = f"Sorry, an error occurred: {str(e)}"
#             self._send_message(error_msg)
#             print(f"Error in GitHub API handler: {str(e)}")
    
#     def _send_message(self, message):
#         """
#         Send a message in the current chat
        
#         Args:
#             message (str): The message to send
#         """
#         try:
#             # Find the message input box
#             input_box = self.driver.find_element(By.XPATH, "//div[@contenteditable='true']")
            
#             # Split long messages into chunks to avoid issues with large messages
#             MAX_CHUNK_SIZE = 1000
#             chunks = [message[i:i+MAX_CHUNK_SIZE] for i in range(0, len(message), MAX_CHUNK_SIZE)]
            
#             for chunk in chunks:
#                 # Clear any existing text
#                 input_box.clear()
                
#                 # Type the message (using send_keys for better compatibility)
#                 input_box.send_keys(chunk)
                
#                 # Send the message
#                 input_box.send_keys(Keys.ENTER)
                
#                 # Small delay between chunks if sending multiple
#                 if len(chunks) > 1:
#                     time.sleep(1)
                
#             print(f"Message sent: {message[:50]}...")  # Print first 50 chars of the message
#         except Exception as e:
#             print(f"Error sending message: {str(e)}")

# def main():
#     """Main function to start the WhatsApp bot"""
#     # Print the environment mode
#     print(f"Starting WhatsApp bot in {ENVIRONMENT.upper()} mode...")
    
#     try:
#         # Initialize the WhatsApp bot
#         bot = WhatsAppBot()
        
#         # Start listening for messages
#         bot.listen_for_messages()
#     except KeyboardInterrupt:
#         print("Bot stopped by user")
#     except Exception as e:
#         print(f"Error running WhatsApp bot: {str(e)}")

# if __name__ == "__main__":
#     main()