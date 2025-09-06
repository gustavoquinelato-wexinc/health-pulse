import sys
import os
import re
import datetime
import pypdf
import docx
from openai import OpenAI
import pandas as pd

# Obter o caminho absoluto do diretório do script atual (subfolder/)
current_script_dir = os.path.dirname(os.path.abspath(__file__))

# Obter o caminho absoluto do diretório pai (solution_root/)
root_dir = os.path.dirname(current_script_dir)

# Adicionar o root_dir ao sys.path se ainda não estiver lá
if root_dir not in sys.path:
    sys.path.append(root_dir)

from helper import MappingHelper
from jira_client import JiraAPITenant
from app_config import AppConfig
from env_loader import get_env_var


class EpicAnalyzer:
    """
    Analyzes Jira epics using WEX AI Gateway based on knowledge documents.
    Loads configuration using AppConfig.
    """
    def __init__(self):
        print("Initializing Epic Analyzer...")
        self.config = self._load_configuration()
        self._validate_config()

        # --- Configuration Values ---
        # Jira Config (Loaded)
        self.jira_url = self.config.get("jira_url")
        self.jira_username = self.config.get("jira_username")
        self.jira_api_token = self.config.get("jira_api_token")
        # Determine jira_scope - Hardcoded for now as GUI logic isn't available
        # Change this if needed or load from config if available
        self.jira_scope = "benefits"
        self.jira_app_param = None # Standalone script, no GUI app object

        # AI Gateway Config
        self.ai_gateway_base_url = get_env_var("AI_GATEWAY_BASE_URL")
        self.ai_gateway_api_key = get_env_var("AI_GATEWAY_API_KEY")
        self.ai_model = get_env_var("AI_MODEL")

        # Document Paths
        self.assets_folder = "./.assets/gems/"
        self.pdf_filename = "epic_and_pi_evaluation_knowledge_source.pdf"
        self.docx_filename = "epic_health_coach.docx"
        self.rating_docx_filename = "ai_model_coaching_document_for_prodiv_rating.docx"
        self.innovation_filename = "innovation_horizons_framework.txt"
        self.pdf_filepath = os.path.join(self.assets_folder, self.pdf_filename)
        self.docx_filepath = os.path.join(self.assets_folder, self.docx_filename)
        self.rating_docx_filepath = os.path.join(self.assets_folder, self.rating_docx_filename)
        self.innovation_filepath = os.path.join(self.assets_folder, self.innovation_filename)

        # Output Folder
        self.output_folder = "./.outputs/"
        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)

        # Jira Projects to Query
        self.benefits_project_keys = ['bex', 'ben', 'bst', 'eppv', 'hba', 'hdo', 'hds', 'fg', 'epe']

        # --- Initialized Tenants ---
        self.jira_client = self._initialize_jira_client()
        self.ai_client = self._initialize_ai_client()

        # --- Loaded Knowledge Content ---
        self.pdf_knowledge_content = None
        self.docx_knowledge_content = None
        self.rating_docx_knowledge_content = None
        self.innovation_knowledge_content = None

    def _load_configuration(self):
        """Loads configuration using AppConfig."""
        try:
            print("Loading configuration from AppConfig...")
            config = AppConfig.load_config()
            print("Configuration loaded successfully.")
            return config
        except Exception as e:
            print(f"FATAL ERROR: Could not load configuration using AppConfig. {e}")
            exit()

    def _validate_config(self):
        """Validates that required configuration values are present."""
        required_jira_keys = ["jira_url", "jira_username", "jira_api_token"]
        missing_keys = [key for key in required_jira_keys if not self.config.get(key)]
        if missing_keys:
            print(f"FATAL ERROR: Missing required Jira configuration key(s) in AppConfig: {', '.join(missing_keys)}")
            exit()
        # Add validation for other required keys if necessary

    def _initialize_jira_client(self):
        """Initializes the JiraAPITenant."""
        print("Initializing Jira client...")
        try:
            client = JiraAPITenant(
                jira_scope=self.jira_scope,
                jira_url=self.jira_url,
                username=self.jira_username,
                api_token=self.jira_api_token,
                app=self.jira_app_param # Passing None as no GUI app object
            )
            print("Jira client initialized successfully.")
            return client
        except Exception as e:
            print(f"FATAL ERROR: Failed to initialize JiraAPITenant: {e}")
            exit()

    def _initialize_ai_client(self):
        """Initializes the OpenAI client for the AI Gateway."""
        print("Initializing AI Gateway client...")
        if not self.ai_gateway_api_key:
             print("\nWarning: No AI Gateway API Key found. Please set AI_GATEWAY_API_KEY environment variable or add 'ai_gateway_api_key' to AppConfig.")

        try:
            client = OpenAI(
                base_url=self.ai_gateway_base_url,
                api_key=self.ai_gateway_api_key,
            )
            print("AI Gateway client initialized successfully.")
            return client
        except Exception as e:
            print(f"FATAL ERROR: Failed to initialize OpenAI client: {e}")
            exit()

    def _read_knowledge_documents(self):
        """Reads content from PDF and DOCX knowledge documents."""
        print("\nReading knowledge documents...")
        self.pdf_knowledge_content = self._read_pdf_text(self.pdf_filepath)
        self.docx_knowledge_content = self._read_docx_text(self.docx_filepath)
        self.rating_docx_knowledge_content = self._read_docx_text(self.rating_docx_filepath)
        self.innovation_knowledge_content = self._read_text_file(self.innovation_filepath)

        if self.pdf_knowledge_content is None or self.docx_knowledge_content is None or self.rating_docx_knowledge_content is None:
            print("FATAL ERROR: Could not read one or more core knowledge documents. Exiting.")
            exit()

        if self.innovation_knowledge_content is None:
            print("Warning: Could not read Innovation Horizons framework document. Portfolio analysis will be limited.")
            # Create a basic version of the framework content
            self.innovation_knowledge_content = """
            # McKinsey Innovation Horizons Framework

            ## The Three Horizons

            ### Horizon 1 (H1): Core Business Optimization
            - Focus: Extending and defending core businesses
            - Timeframe: Immediate to short-term (0-1 years)
            - Risk Level: Low
            - Ideal Portfolio Allocation: ~70%

            ### Horizon 2 (H2): Emerging Opportunities
            - Focus: Building emerging businesses and opportunities
            - Timeframe: Medium-term (1-3 years)
            - Risk Level: Moderate
            - Ideal Portfolio Allocation: ~20%

            ### Horizon 3 (H3): Disruptive Innovations
            - Focus: Creating viable options for future business
            - Timeframe: Long-term (3+ years)
            - Risk Level: High
            - Ideal Portfolio Allocation: ~10%
            """

        print("Knowledge documents read successfully.")

    def _read_pdf_text(self, filepath):
        """Extracts text content from a PDF file."""
        try:
            reader = pypdf.PdfReader(filepath)
            text = "".join(page.extract_text() + "\n" for page in reader.pages if page.extract_text())
            print(f"Successfully read text from PDF: {filepath}")
            return text
        except FileNotFoundError:
            print(f"Error: PDF file not found at {filepath}")
            return None
        except Exception as e:
            print(f"Error reading PDF file {filepath}: {e}")
            return None

    def _read_docx_text(self, filepath):
        """Extracts text content from a DOCX file."""
        try:
            document = docx.Document(filepath)
            text = "\n".join([para.text for para in document.paragraphs])
            print(f"Successfully read text from DOCX: {filepath}")
            return text
        except FileNotFoundError:
            print(f"Error: DOCX file not found at {filepath}")
            return None
        except Exception as e:
            print(f"Error reading DOCX file {filepath}: {e}")
            return None

    def _read_text_file(self, filepath):
        """Reads content from a text file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                text = file.read()
            print(f"Successfully read text from file: {filepath}")
            return text
        except FileNotFoundError:
            print(f"Error: Text file not found at {filepath}")
            return None
        except Exception as e:
            print(f"Error reading text file {filepath}: {e}")
            return None

    def _remove_markdown(self, text):
        """
        Remove markdown formatting from text.

        Args:
            text: The text containing markdown formatting

        Returns:
            Text with markdown formatting removed
        """
        if not text:
            return ""

        # Remove bold markdown (**text**)
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)

        # Remove italic markdown (*text*)
        text = re.sub(r'\*(.*?)\*', r'\1', text)

        # Remove other markdown formatting if needed
        # Add more substitutions here if other markdown elements are present

        return text

    def fetch_epics_from_jira(self, project_keys):
        """Fetches epics (key, summary, description) from specified Jira projects."""
        epics_data = []
        project_keys_str = ", ".join([f"'{key.upper()}'" for key in project_keys])
        jql_query = f"project IN ({project_keys_str}) AND issuetype = Epic and statusCategory != Done ORDER BY key ASC"

        print(f"\nFetching epics with JQL: {jql_query}")
        try:
            # Adjust date params if required by your specific get_issues implementation
            issues = self.jira_client.get_issues(jql_query=jql_query, start_date=None, end_date=None)
            smh = MappingHelper()

            for issue in issues:
                epic_key = issue.get('key')
                summary = issue.get('fields', {}).get('summary', 'N/A')
                description = issue.get('fields', {}).get('description', 'N/A')
                if description is None: description = 'N/A'

                original_status = issue.get('fields', {}).get('status', {}).get('name', '')
                mapped_status = smh.get_mapped_status_value(original_status)

                epics_data.append({
                    'key': epic_key,
                    'summary': summary,
                    'description': description,
                    'mapped_status': mapped_status
                })
            print(f"Fetched {len(epics_data)} epics from Jira.")
            return epics_data
        except Exception as e:
            print(f"Error fetching epics from Jira: {e}")
            return [] # Return empty list on error

    def _get_ai_analysis_and_rating(self, epic_summary, epic_description, include_portfolio_analysis=True, max_retries=3, initial_retry_delay=2):
        """
        Sends data to AI Gateway and parses the response for a single epic.
        Includes retry logic for handling rate limiting errors.

        Args:
            epic_summary: The summary of the epic
            epic_description: The description of the epic
            include_portfolio_analysis: Whether to include portfolio analysis in the prompt
            max_retries: Maximum number of retry attempts (default: 3)
            initial_retry_delay: Initial delay in seconds before retrying (default: 2)
                                Will be doubled for each subsequent retry (exponential backoff)
        """
        if self.pdf_knowledge_content is None or self.docx_knowledge_content is None or self.rating_docx_knowledge_content is None:
             print("Error: Knowledge documents not loaded.")
             return "Error: Knowledge documents not loaded.", "Error", "Knowledge documents not loaded.", {}

        # Base prompt for quality analysis
        base_prompt = f"""
Based on the attached Product Innovation Velocity documents provided below, what can you tell me about the quality of the following epics? Also rank its quality from 0-10, where 0 is very poor and 10 is excellent.

IMPORTANT INSTRUCTIONS:
1. Use KNOWLEDGE DOCUMENT 1 ({self.pdf_filename}) for general epic evaluation criteria
2. Use KNOWLEDGE DOCUMENT 2 ({self.docx_filename}) for health check guidelines
3. SPECIFICALLY USE KNOWLEDGE DOCUMENT 3 ({self.rating_docx_filename}) for determining the numeric rating (0-10) - this document contains the specific scoring guidelines you must follow

Epic Summary:
{epic_summary}

Epic Description:
{epic_description}

--- START KNOWLEDGE DOCUMENT 1 ({self.pdf_filename}) CONTENT ---
{self.pdf_knowledge_content}
--- END KNOWLEDGE DOCUMENT 1 ({self.pdf_filename}) CONTENT ---

--- START KNOWLEDGE DOCUMENT 2 ({self.docx_filename}) CONTENT ---
{self.docx_knowledge_content}
--- END KNOWLEDGE DOCUMENT 2 ({self.docx_filename}) CONTENT ---

--- START KNOWLEDGE DOCUMENT 3 ({self.rating_docx_filename}) CONTENT - SCORING GUIDELINES ---
{self.rating_docx_knowledge_content}
--- END KNOWLEDGE DOCUMENT 3 ({self.rating_docx_filename}) CONTENT - SCORING GUIDELINES ---
"""

        # Portfolio analysis extension
        portfolio_prompt = ""
        if include_portfolio_analysis and self.innovation_knowledge_content:
            portfolio_prompt = f"""
ADDITIONAL TASK - PORTFOLIO ANALYSIS:
4. Use KNOWLEDGE DOCUMENT 4 {self.innovation_filename} to classify this epic into one of the three innovation horizons (H1, H2, or H3)
5. Provide a risk score (1-10), value score (1-10), and innovation index (1-10) for this epic
   - IMPORTANT: For the innovation index, strictly follow the "Innovation Index Scoring Guidelines (1-10 Scale)" section in the framework document
   - Make sure to consider all five scoring factors listed in the guidelines
6. Justify your classification and scores with specific references to the epic content

--- START KNOWLEDGE DOCUMENT 4 {self.innovation_filename} CONTENT ---
{self.innovation_knowledge_content}
--- END KNOWLEDGE DOCUMENT 4 {self.innovation_filename} CONTENT ---
"""

        # Response format instructions
        format_instructions = """
Please provide your analysis first, and then clearly state the results using this format:

Analysis: [Your detailed analysis here...]
Rank: [Your 0-10 quality rank here]
"""

        # Add portfolio format instructions if needed
        if include_portfolio_analysis:
            format_instructions += """
Horizon: [H1/H2/H3]
Risk: [1-10]
Value: [1-10]
Innovation: [1-10]
Portfolio Justification: [Brief justification for horizon classification and scores]

IMPORTANT ANALYSIS GUIDELINES:
1. DO NOT classify horizons based solely on keywords like "AI", "blockchain", or "innovation" in the epic title or description
2. Look beyond buzzwords and assess the ACTUAL innovation level based on what the epic is trying to accomplish
3. Consider the CONTEXT of the organization - what might be H3 for one company could be H1 for a tech leader
4. Evaluate the SUBSTANCE of the proposed changes, not just the technology mentioned
5. Assess whether the epic represents a true business model change or just an incremental improvement with trendy terminology
"""

        # Combine all parts of the prompt
        prompt = base_prompt + portfolio_prompt + format_instructions
        # Initialize retry counter and delay
        retry_count = 0
        retry_delay = initial_retry_delay

        while True:
            try:
                chat_completion = self.ai_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "You are an expert analyst reviewing project epics based on provided documentation."},
                        {"role": "user", "content": prompt}
                    ],
                    model=self.ai_model,
                    temperature=0.3,
                    max_tokens=700
                )

                # Get the raw response text
                raw_response_text = chat_completion.choices[0].message.content if chat_completion.choices else ""

                # Store the raw response for debugging purposes
                original_response = raw_response_text

                # Remove markdown formatting from the response
                full_response_text = self._remove_markdown(raw_response_text)

                # Parse analysis and rating
                analysis = "N/A"
                rating = "N/A"
                horizon = "N/A"
                risk_score = "N/A"
                value_score = "N/A"
                innovation_index = "N/A"
                portfolio_justification = "N/A"

                # Extract quality rating - now using simpler patterns since markdown is removed
                rating_match = re.search(r"Rank:\s*(\d+(?:\.\d+)?)", full_response_text)
                if rating_match:
                    try:
                        rating_float = float(rating_match.group(1))
                        rating = rating_float if 0 <= rating_float <= 10 else f"Invalid value: {rating_match.group(1)}"
                    except ValueError:
                        rating = 0  # Default to 0 for non-numeric values
                        print(f"  -> Warning: Non-numeric rating value '{rating_match.group(1)}' converted to 0")
                    analysis = full_response_text[:rating_match.start()].strip()
                    if not analysis: analysis = full_response_text[rating_match.end():].strip() # Try text after rank
                else:
                    # Try a more general pattern if the specific one didn't match
                    general_rating_match = re.search(r"[Rr]ank.*?(\d+(?:\.\d+)?)", full_response_text)
                    if general_rating_match:
                        try:
                            rating = float(general_rating_match.group(1))
                        except ValueError:
                            rating = 0
                            print(f"  -> Warning: Non-numeric rating value converted to 0")
                    else:
                        analysis = full_response_text.strip() # Assume whole response is analysis if rank format not found
                        rating = 0  # Default to 0 if no rating found
                        print(f"  -> Warning: No rating found in response, defaulting to 0")

                if not analysis and full_response_text: analysis = full_response_text.strip() # Fallback

                # Extract portfolio analysis data if included - using simpler patterns
                horizon_match = re.search(r"Horizon:\s*(H[123])", full_response_text, re.IGNORECASE)
                if horizon_match:
                    horizon = horizon_match.group(1).upper()
                else:
                    # Try a more general pattern
                    general_horizon_match = re.search(r"[Hh]orizon.*?(H[123])", full_response_text)
                    if general_horizon_match:
                        horizon = general_horizon_match.group(1).upper()
                    else:
                        horizon = "H1"  # Default to H1 if not found
                        print(f"  -> Warning: No horizon found in response, defaulting to H1")

                # Extract risk score
                risk_match = re.search(r"Risk:\s*(\d+(?:\.\d+)?)", full_response_text)
                if risk_match:
                    try:
                        risk_score = float(risk_match.group(1))
                    except ValueError:
                        risk_score = 0  # Default to 0 for non-numeric values
                        print(f"  -> Warning: Non-numeric risk value converted to 0")
                else:
                    # Try a more general pattern
                    general_risk_match = re.search(r"[Rr]isk.*?(\d+(?:\.\d+)?)", full_response_text)
                    if general_risk_match:
                        try:
                            risk_score = float(general_risk_match.group(1))
                        except ValueError:
                            risk_score = 0
                    else:
                        risk_score = 0  # Default to 0 if not found
                        print(f"  -> Warning: No risk score found in response, defaulting to 0")

                # Extract value score
                value_match = re.search(r"Value:\s*(\d+(?:\.\d+)?)", full_response_text)
                if value_match:
                    try:
                        value_score = float(value_match.group(1))
                    except ValueError:
                        value_score = 0  # Default to 0 for non-numeric values
                        print(f"  -> Warning: Non-numeric value score converted to 0")
                else:
                    # Try a more general pattern
                    general_value_match = re.search(r"[Vv]alue.*?(\d+(?:\.\d+)?)", full_response_text)
                    if general_value_match:
                        try:
                            value_score = float(general_value_match.group(1))
                        except ValueError:
                            value_score = 0
                    else:
                        value_score = 0  # Default to 0 if not found
                        print(f"  -> Warning: No value score found in response, defaulting to 0")

                # Extract innovation index
                innovation_match = re.search(r"Innovation:\s*(\d+(?:\.\d+)?)", full_response_text)
                if innovation_match:
                    try:
                        innovation_index = float(innovation_match.group(1))
                    except ValueError:
                        innovation_index = 0  # Default to 0 for non-numeric values
                        print(f"  -> Warning: Non-numeric innovation value converted to 0")
                else:
                    # Try a more general pattern
                    general_innovation_match = re.search(r"[Ii]nnovation.*?(\d+(?:\.\d+)?)", full_response_text)
                    if general_innovation_match:
                        try:
                            innovation_index = float(general_innovation_match.group(1))
                        except ValueError:
                            innovation_index = 0
                    else:
                        innovation_index = 0  # Default to 0 if not found
                        print(f"  -> Warning: No innovation index found in response, defaulting to 0")

                # Extract portfolio justification
                portfolio_match = re.search(r"Portfolio Justification:(.*?)(?=\n\n|\Z)", full_response_text, re.DOTALL | re.IGNORECASE)
                if portfolio_match:
                    portfolio_justification = portfolio_match.group(1).strip()
                else:
                    # Try a more general pattern
                    general_portfolio_match = re.search(r"[Pp]ortfolio [Jj]ustification.*?\n(.*?)(?=\n\n|\Z)", full_response_text, re.DOTALL)
                    if general_portfolio_match:
                        portfolio_justification = general_portfolio_match.group(1).strip()
                    else:
                        portfolio_justification = "No justification provided"
                        print(f"  -> Warning: No portfolio justification found in response")

                # Ensure all numeric values are properly formatted
                # Convert any remaining "N/A" values to 0 for numeric fields
                if isinstance(rating, str) and rating != "N/A":
                    try:
                        rating = float(rating)
                    except ValueError:
                        rating = 0
                        print(f"  -> Warning: Invalid rating value converted to 0")
                elif rating == "N/A":
                    rating = 0
                    print(f"  -> Warning: 'N/A' rating value converted to 0")

                # Ensure all numeric scores are proper numbers, not strings
                for score_name, score_value in [("risk_score", risk_score), ("value_score", value_score), ("innovation_index", innovation_index)]:
                    if isinstance(score_value, str) and score_value != "N/A":
                        try:
                            locals()[score_name] = float(score_value)
                        except ValueError:
                            locals()[score_name] = 0
                            print(f"  -> Warning: Invalid {score_name} value converted to 0")
                    elif score_value == "N/A":
                        locals()[score_name] = 0
                        print(f"  -> Warning: 'N/A' {score_name} value converted to 0")

                # Update the variables after the loop
                risk_score = locals()["risk_score"]
                value_score = locals()["value_score"]
                innovation_index = locals()["innovation_index"]

                # Return all extracted data
                portfolio_data = {
                    "horizon": horizon,
                    "risk_score": risk_score,
                    "value_score": value_score,
                    "innovation_index": innovation_index,
                    "portfolio_justification": portfolio_justification
                }

                # Use the cleaned text for analysis but keep the original response for raw_ai_response
                return analysis, rating, original_response, portfolio_data

            except Exception as e:
                error_str = str(e)

                # Check if this is a rate limit error (HTTP 429)
                is_rate_limit_error = "429" in error_str or "rate limit" in error_str.lower() or "throttling_error" in error_str.lower()

                # Increment retry counter
                retry_count += 1

                # If we've exceeded max retries or it's not a rate limit error, raise the exception
                if retry_count > max_retries or not is_rate_limit_error:
                    print(f"  -> Error during AI Gateway call or parsing (attempt {retry_count}/{max_retries}): {e}")
                    empty_portfolio_data = {
                        "horizon": "H1",  # Default to H1 on error
                        "risk_score": 0,  # Default to 0 on error
                        "value_score": 0,  # Default to 0 on error
                        "innovation_index": 0,  # Default to 0 on error
                        "portfolio_justification": f"Error in AI processing: {str(e)}"
                    }
                    return "Error in AI processing.", 0, str(e), empty_portfolio_data

                # Otherwise, wait and retry
                print(f"  -> Rate limit error encountered (attempt {retry_count}/{max_retries}). Retrying in {retry_delay} seconds...")
                import time
                time.sleep(retry_delay)

                # Exponential backoff - double the delay for next retry
                retry_delay *= 2

    def _process_epic_with_ai(self, epic, include_portfolio_analysis=True):
        """
        Process a single epic with AI Gateway in a thread-safe manner.

        Args:
            epic: The epic data dictionary
            include_portfolio_analysis: Whether to include portfolio analysis
        """
        try:
            print(f"  Processing epic {epic['key']} - {epic['summary'][:50]}...")

            # Extract project key from epic key
            epic_key = epic['key']
            project_key = epic_key[:2] if len(epic_key) > 2 and epic_key[2] == '-' else epic_key[:3]
            epic['project_key'] = project_key

            # Get AI analysis with portfolio data if requested
            ai_analysis, ai_rating, raw_ai_response, portfolio_data = self._get_ai_analysis_and_rating(
                epic['summary'],
                epic['description'],
                include_portfolio_analysis=include_portfolio_analysis
            )

            # Add basic analysis data - ensure analysis text is also cleaned of markdown
            epic['ai_analysis'] = self._remove_markdown(ai_analysis)
            epic['ai_rating'] = ai_rating
            epic['raw_ai_response'] = raw_ai_response

            # Add portfolio analysis data if included
            if include_portfolio_analysis:
                epic['horizon'] = portfolio_data['horizon']
                epic['risk_score'] = portfolio_data['risk_score']
                epic['value_score'] = portfolio_data['value_score']
                epic['innovation_index'] = portfolio_data['innovation_index']
                # Ensure portfolio justification is also cleaned of markdown
                epic['portfolio_justification'] = self._remove_markdown(portfolio_data['portfolio_justification'])

                print(f"  -> Epic {epic['key']} - Rating: {ai_rating}, Horizon: {portfolio_data['horizon']}")
            else:
                print(f"  -> Epic {epic['key']} - Rating: {ai_rating}")

            return epic
        except Exception as e:
            print(f"  -> Error processing epic {epic['key']}: {e}")
            epic['ai_analysis'] = f"Error: {str(e)}"
            epic['ai_rating'] = 0  # Default to 0 on error instead of "Error" string
            epic['raw_ai_response'] = f"Error: {str(e)}"

            if include_portfolio_analysis:
                epic['horizon'] = "H1"  # Default to H1 on error
                epic['risk_score'] = 0  # Default to 0 on error
                epic['value_score'] = 0  # Default to 0 on error
                epic['innovation_index'] = 0  # Default to 0 on error
                epic['portfolio_justification'] = f"Error: {str(e)}"

            return epic

    def run_analysis(self, include_portfolio_analysis=True):
        """
        Main execution flow.

        Args:
            include_portfolio_analysis: Whether to include portfolio analysis
        """
        print("\nStarting Epic Analysis Process...")
        start_time = datetime.datetime.now()

        # 1. Load knowledge documents (only once)
        self._read_knowledge_documents()

        # 2. Fetch Epics
        all_epics = self.fetch_epics_from_jira(self.benefits_project_keys)
        if not all_epics:
            print("No epics fetched or error occurred. Exiting.")
            return

        # 3. Process Epics using ThreadPoolExecutor for parallel processing
        print(f"\nProcessing {len(all_epics)} epics with AI Gateway using parallel threads...")

        # Create a lock for thread-safe progress updates
        from threading import Lock
        progress_lock = Lock()

        # Track progress
        processed_count = 0
        total_epics = len(all_epics)

        # Function to update progress after each epic is processed
        def update_progress(result):
            nonlocal processed_count
            with progress_lock:
                processed_count += 1
                progress_percent = (processed_count / total_epics) * 100
                print(f"Progress: {processed_count}/{total_epics} epics processed ({progress_percent:.1f}%)")
            return result

        # Process epics in parallel using ThreadPoolExecutor
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Determine optimal number of workers (threads)
        # Too many threads can cause rate limiting or resource issues
        max_workers = min(10, os.cpu_count() * 2)
        print(f"Using ThreadPoolExecutor with {max_workers} workers")

        processed_epics = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all epics for processing
            future_to_epic = {executor.submit(self._process_epic_with_ai, epic, include_portfolio_analysis): epic for epic in all_epics}

            # Process results as they complete
            for future in as_completed(future_to_epic):
                try:
                    processed_epic = future.result()
                    processed_epics.append(processed_epic)
                    update_progress(processed_epic)
                except Exception as e:
                    epic = future_to_epic[future]
                    print(f"  -> Error in thread processing epic {epic['key']}: {e}")
                    # Add the epic with error information
                    epic['ai_analysis'] = f"Thread error: {str(e)}"
                    epic['ai_rating'] = 0  # Default to 0 on error
                    epic['raw_ai_response'] = f"Thread error: {str(e)}"

                    # Add portfolio error data if needed
                    if include_portfolio_analysis:
                        epic['horizon'] = "H1"  # Default to H1 on error
                        epic['risk_score'] = 0  # Default to 0 on error
                        epic['value_score'] = 0  # Default to 0 on error
                        epic['innovation_index'] = 0  # Default to 0 on error
                        epic['portfolio_justification'] = f"Thread error: {str(e)}"

                    processed_epics.append(epic)
                    update_progress(epic)

        # 4. Save Final Results
        print("\nSaving final results to Excel...")
        if processed_epics:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_filename = f"innovation_portfolio_analysis_{timestamp}.xlsx"
            self._save_results_to_excel(processed_epics, excel_filename)
        else:
            print("No epics were processed to save.")

        end_time = datetime.datetime.now()
        total_duration_seconds = (end_time - start_time).total_seconds()

        # Format duration as HH:MM:ss
        hours, remainder = divmod(int(total_duration_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        time_format = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        # Also calculate minutes for backward compatibility
        total_duration_minutes = total_duration_seconds / 60

        print(f"\nEpic Analysis Process Completed in {time_format} (HH:MM:ss)")
        print(f"Total processing time: {total_duration_minutes:.2f} minutes")

    def _save_results_to_excel(self, epics, filename_base):
        """Helper method to save results to Excel."""
        try:
            df = pd.DataFrame(epics)
            # Reorder columns as specified:
            # Column A = key
            # Column B = project_key
            # Column C = summary
            # Column D = description
            # Column E = mapped_status
            # Column F = ai_analysis
            # Column G = ai_rating
            # Column H = horizon
            # Column I = risk_score
            # Column J = value_score
            # Column K = innovation_index
            # Column L = portfolio_justification
            cols_order = ['key', 'project_key', 'summary', 'description', 'mapped_status', 'ai_analysis', 'ai_rating']

            # Add portfolio analysis columns if they exist
            portfolio_cols = ['horizon', 'risk_score', 'value_score', 'innovation_index', 'portfolio_justification']
            for col in portfolio_cols:
                if col in df.columns:
                    cols_order.append(col)

            # Add any remaining columns (except raw_ai_response) at the end
            remaining_cols = [col for col in df.columns if col not in cols_order and col != 'raw_ai_response']

            # Optionally add raw_ai_response at the very end if needed
            if 'raw_ai_response' in df.columns:
                remaining_cols.append('raw_ai_response')

            # Combine the ordered columns with any remaining columns
            final_cols = cols_order + remaining_cols

            # Filter to only include columns that actually exist in the dataframe
            final_cols = [col for col in final_cols if col in df.columns]

            # Reorder the dataframe columns
            df = df[final_cols]

            excel_filepath = os.path.join(self.output_folder, f"{filename_base}")
            df.to_excel(excel_filepath, index=False, engine='openpyxl')
            print(f"Successfully saved results to: {excel_filepath}")
            return True
        except Exception as e:
            print(f"Error saving Excel file: {e}")
            return False

# --- Main Execution ---
if __name__ == "__main__":
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Analyze epics using WEX AI Gateway')
    parser.add_argument('--no-portfolio', action='store_true', help='Skip portfolio analysis')
    args = parser.parse_args()

    analyzer = EpicAnalyzer()
    analyzer.run_analysis(include_portfolio_analysis=not args.no_portfolio)