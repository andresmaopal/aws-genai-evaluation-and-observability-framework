import os
import logging
import sys
import argparse
from opentelemetry import baggage, context

def parse_arguments():
    parser = argparse.ArgumentParser(description='Strands Travel Agent with Session Tracking')
    parser.add_argument('--session-id', 
                       type=str, 
                       required=True,
                       help='Session ID to associate with this agent run')
    return parser.parse_args()

def set_session_context(session_id):
    """Set the session ID in OpenTelemetry baggage for trace correlation"""
    ctx = baggage.set_baggage("session.id", session_id)
    token = context.attach(ctx)
    logging.info(f"Session ID '{session_id}' attached to telemetry context")
    return token

###########################
#### Agent Code below: ####
###########################

import os
import logging
from strands import Agent, tool
from strands.models import BedrockModel
from ddgs import DDGS
from strands_tools import retrieve, current_time
from strands.models.bedrock import BedrockModel
import boto3

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Strands logging
logging.getLogger("strands").setLevel(logging.INFO)

@tool
def RestaurantScoutAgent(query):
    print("Calling Bedrock Restaurant Scout Agent")
    
    region = "us-east-1"
    agent_id = "CD5T9SHCNP"
    alias_id = "K0SGAE62WN"
    
    print(f"Region: {region}, Agent ID: {agent_id}, Alias ID: {alias_id}")

    bedrock_agent_runtime_client = boto3.client("bedrock-agent-runtime", region_name=region)
    session_id = str(uuid.uuid1())
    end_session = False
    enable_trace = True

    # invoke the agent API
    try:
        agentResponse = bedrock_agent_runtime_client.invoke_agent(
            inputText=query,
            agentId=agent_id,
            agentAliasId=alias_id, 
            sessionId=session_id,
            enableTrace=enable_trace, 
            endSession=end_session,
        )
        
        event_stream = agentResponse['completion']
        agent_answer = ""
        for event in event_stream:        
            if 'chunk' in event:
                data = event['chunk']['bytes']
                agent_answer += data.decode('utf8')
            else:
                print(f"Unexpected event: {event}")
        
        return agent_answer
    except Exception as e:
        print(f"Error invoking Bedrock agent: {e}")
        return f"Error: {str(e)}"

@tool
def ActivityFinderAgent(query):
    print("CALLING BEDROCK ACTIVITY FINDER")
    
    region = "us-east-1"
    agent_id = "ULSJ8ADVZT"
    alias_id = "5DGSYX3ZYF"
    
    print(f"Region: {region}, Agent ID: {agent_id}, Alias ID: {alias_id}")

    bedrock_agent_runtime_client = boto3.client("bedrock-agent-runtime", region_name=region)
    session_id = str(uuid.uuid1())
    end_session = False
    enable_trace = True

    # invoke the agent API
    try:
        agentResponse = bedrock_agent_runtime_client.invoke_agent(
            inputText=query,
            agentId=agent_id,
            agentAliasId=alias_id, 
            sessionId=session_id,
            enableTrace=enable_trace, 
            endSession=end_session,
        )
        
        event_stream = agentResponse['completion']
        agent_answer = ""
        for event in event_stream:        
            if 'chunk' in event:
                data = event['chunk']['bytes']
                agent_answer += data.decode('utf8')
            else:
                print(f"Unexpected event: {event}")
        
        return agent_answer
    except Exception as e:
        print(f"Error invoking Bedrock agent: {e}")
        return f"Error: {str(e)}"

@tool
def ItineraryCompilerAgent(query):
    print("CALLING BEDROCK ITINEARY COMPILER AGENT")
    
    region = "us-east-1"
    agent_id = "Y70D35MBRT"
    alias_id = "9FCYAKQQQX"
    
    print(f"Region: {region}, Agent ID: {agent_id}, Alias ID: {alias_id}")

    bedrock_agent_runtime_client = boto3.client("bedrock-agent-runtime", region_name=region)
    session_id = str(uuid.uuid1())
    end_session = False
    enable_trace = True

    # invoke the agent API
    try:
        agentResponse = bedrock_agent_runtime_client.invoke_agent(
            inputText=query,
            agentId=agent_id,
            agentAliasId=alias_id, 
            sessionId=session_id,
            enableTrace=enable_trace, 
            endSession=end_session,
        )
        
        event_stream = agentResponse['completion']
        agent_answer = ""
        for event in event_stream:        
            if 'chunk' in event:
                data = event['chunk']['bytes']
                agent_answer += data.decode('utf8')
            else:
                print(f"Unexpected event: {event}")
        
        return agent_answer
    except Exception as e:
        print(f"Error invoking Bedrock agent: {e}")
        return f"Error: {str(e)}"
        

def get_bedrock_model():
    model_id = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0")
    region = os.getenv("AWS_DEFAULT_REGION", "us-west-2")
    
    try:
        bedrock_model = BedrockModel(
            model_id=model_id,
            region_name=region,
            temperature=0.0,
            max_tokens=1024
        )
        logger.info(f"Successfully initialized Bedrock model: {model_id} in region: {region}")
        return bedrock_model
    except Exception as e:
        logger.error(f"Failed to initialize Bedrock model: {str(e)}")
        logger.error("Please ensure you have proper AWS credentials configured and access to the Bedrock model")
        raise

# Initialize the model
bedrock_model = get_bedrock_model()

# Create the travel agent
travel_agent = Agent(
    model=bedrock_model,
    system_prompt="""As a Trip Planner, you take advantage of your specialists agents 
(activity_planner, restaurant_scout, and itinerary_compiler) at planning activities and finding good restaurants. 
You also create itineraries to package all of that in a clear plan.""",
    tools = [RestaurantScoutAgent,ActivityFinderAgent,ItineraryCompilerAgent],
    trace_attributes={
    "user.id": "user@domain.com",
    "tags": ["Strands", "Observability"],
}

)

# Execute the travel research task
query="""
    Find highly-rated restaurants and dining experiences at {destination}.
    Use internet search tools, restaurant review sites, and travel guides.
    Make sure to find a variety of options to suit different tastes and budgets, and ratings for them.

    Traveler's information:

    - origin: Mexico City
    - destination: Medellin
    - age of the traveler: 40
    - hotel localtion: Medellin, Marriott Hotel
    - arrival: 15 December 2025
    - departure: 3 January 2026
    - food preferences: Sushi, Thai
"""

result = travel_agent(query)
print("Result:", result)
