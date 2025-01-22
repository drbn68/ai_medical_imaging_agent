import os
import base64
import streamlit as st
from PIL import Image
from typing import Annotated
from typing_extensions import TypedDict

# --- LangChain & Tools ---
from langchain_openai import ChatOpenAI
from langchain_community.tools import DuckDuckGoSearchRun  # For DuckDuckGo search integration

# --- LangGraph ---
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition


# ------------------------------------------------------------
# 1) Define the LangGraph State
# ------------------------------------------------------------
class State(TypedDict):
    messages: Annotated[list, add_messages]

# Create a StateGraph
graph_builder = StateGraph(State)

# ------------------------------------------------------------
# 2) Check for required session variable: OPENAI_API_KEY
# ------------------------------------------------------------
if "OPENAI_API_KEY" not in st.session_state:
    st.session_state.OPENAI_API_KEY = None

# ------------------------------------------------------------
# 3) Sidebar: Input field for OpenAI API Key
# ------------------------------------------------------------
with st.sidebar:
    st.title("ℹ️ Configuration")

    if not st.session_state.OPENAI_API_KEY:
        api_key = st.text_input(
            "Enter your OpenAI API Key:",
            type="password"
        )
        st.caption(
            "Get your API key from [OpenAI Platform]"
            "(https://platform.openai.com/account/api-keys) 🔑"
        )
        if api_key:
            st.session_state.OPENAI_API_KEY = api_key
            st.success("API Key saved!")
            st.rerun()
    else:
        st.success("API Key is configured")
        if st.button("🔄 Reset API Key"):
            st.session_state.OPENAI_API_KEY = None
            st.rerun()

    st.info(
        "This tool provides AI-powered analysis of medical imaging data using "
        "advanced computer vision and radiological expertise."
    )
    st.warning(
        "⚠DISCLAIMER: This tool is for educational and informational purposes only. "
        "All analyses should be reviewed by qualified healthcare professionals. "
        "Do not make medical decisions based solely on this analysis."
    )

# ------------------------------------------------------------
# 4) Initialize LangGraph Components
# ------------------------------------------------------------
medical_agent = None
if st.session_state.OPENAI_API_KEY:
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        #model="gpt-4o",
        temperature=0.7,
        openai_api_key=st.session_state.OPENAI_API_KEY,
    )

    ddg_tool = DuckDuckGoSearchRun()  # Initialize DuckDuckGo search tool
    tools = [ddg_tool]
    llm_with_tools = llm.bind_tools(tools)

    # Define the chatbot node
    def chatbot(state: State):
        response = llm_with_tools.invoke(state["messages"])
        #st.write("Debugging: Tool invocation response", response)
        return {"messages": [response]}

    # Add the chatbot and tool nodes to the graph
    graph_builder.add_node("chatbot", chatbot)
    tool_node = ToolNode(tools=tools)
    graph_builder.add_node("tools", tool_node)

    # Define edges between nodes
    graph_builder.add_conditional_edges("chatbot", tools_condition)
    graph_builder.add_edge("tools", "chatbot")
    graph_builder.set_entry_point("chatbot")

    medical_agent = graph_builder.compile()
else:
    st.warning("Please configure your OpenAI API Key in the sidebar to continue.")

# ------------------------------------------------------------
# 5) Define the Prompt/Query
# ------------------------------------------------------------
query = """
You are a highly skilled university professor of radiology and medical imaging with extensive knowledge in diagnostic imaging. 
Explain this image to your students as accurately as possible and structure your response as follows (always only text):

### 1. Image Type & Region
- Specify imaging modality (X-ray/MRI/CT/Ultrasound/etc.)
- Identify the patient's anatomical region and positioning
- Comment on image quality and technical adequacy

### 2. Key Findings
- List primary observations systematically
- Note any abnormalities in the patient's imaging with precise descriptions
- Include measurements and densities where relevant
- Describe location, size, shape, and characteristics
- Rate severity: Normal/Mild/Moderate/Severe

### 3. Diagnostic Assessment
- Provide primary diagnosis with confidence level
- List differential diagnoses in order of likelihood
- Support each diagnosis with observed evidence from the patient's imaging
- Note any critical or urgent findings

### 4. Patient-Friendly Explanation
- Explain the findings in simple, clear language that the patient can understand
- Avoid medical jargon or provide clear definitions
- Include visual analogies if helpful
- Address common patient concerns related to these findings

### 5. Research Context
IMPORTANT: Use the DuckDuckGo search tool to:
- Find recent medical literature about similar cases
- Search for standard treatment protocols
- Provide a list of relevant medical links
- Research any relevant technological advances
- Include 2-3 key references to support your analysis

Format your response using clear markdown headers and bullet points. Be concise yet thorough.
"""

# ------------------------------------------------------------
# 6) Build the Streamlit UI
# ------------------------------------------------------------
st.title("🏥 Medical Imaging Diagnosis Agent")
st.write("Upload a medical image for professional analysis")

upload_container = st.container()
image_container = st.container()
analysis_container = st.container()

with upload_container:
    uploaded_file = st.file_uploader(
        "Upload Medical Image",
        type=["jpg", "jpeg", "png"],
        help="Supported formats: JPG, JPEG, PNG"
    )

if uploaded_file is not None:
    with image_container:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            image = Image.open(uploaded_file)
            image_path = "temp_medical_image.png"
            image.save(image_path)

            # Encode the image to Base64
            with open(image_path, "rb") as img_file:
                encoded_image = base64.b64encode(img_file.read()).decode()

            # Display the image
            st.image(
                image,
                caption="Uploaded Medical Image",
                use_container_width=True
            )

            analyze_button = st.button(
                "🔍 Analyze Image",
                type="primary",
                use_container_width=True
            )

    with analysis_container:
        if analyze_button:
            with st.spinner("🔄 Analyzing image... Please wait."):
                try:
                    if medical_agent:
                        # Prepare the state for the graph
                        state = {
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": query},
                                        {
                                            "type": "image_url",
                                            "image_url": {
                                                "url": f"data:image/png;base64,{encoded_image}",
                                                "detail": "low"
                                            }
                                        }
                                    ]
                                }
                            ]
                        }

                        # Invoke the medical agent
                        result_state = medical_agent.invoke(state)

                        # Debugging: Log the full response structure
                        #st.write("Debugging: Full response from medical agent", result_state)

                        # Extract the response content
                        combined_response = ""
                        for message in result_state["messages"]:
                            # Handle AI response
                            if hasattr(message, "type") and message.type == "ai":
                                if hasattr(message, "content") and message.content:
                                    combined_response += message.content
                            # Handle tool responses
                            elif hasattr(message, "type") and message.type == "tool_call":
                                if hasattr(message, "content") and message.content:
                                    combined_response += f"\n\n### Tool Result:\n{message.content}"

                        # Display the combined response
                        if combined_response.strip():
                            st.markdown("### 📋 Analysis Results")
                            st.markdown(combined_response)
                        else:
                            st.error("AI response content is missing or improperly formatted.")
                    else:
                        st.warning("No agent is configured. Please ensure you have provided your OpenAI key.")
                except Exception as e:
                    st.error(f"Analysis error: {e}")
                finally:
                    # Clean up the temporary file
                    if os.path.exists(image_path):
                        os.remove(image_path)

else:
    st.info("👆 Please upload a medical image to begin analysis")
