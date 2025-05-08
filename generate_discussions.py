import json
import random
from pathlib import Path

def load_tags():
    """Load tags from the tags.json file."""
    tags_file = Path(__file__).parent / "tags.json"
    data = json.loads(tags_file.read_text())
    return data.get("labels", [])

def generate_discussion_questions(tags, num_questions_per_tag=2):
    """Generate discussion questions based on each tag."""
    questions = {}
    
    # Question templates for each tag category
    azure_ai_templates = [
        "What are the best practices for implementing {topic} in production environments?",
        "How do you handle scalability challenges when working with {topic}?",
        "What security considerations should be prioritized when implementing {topic}?",
        "How does {topic} compare to similar offerings from other cloud providers?",
        "What's your experience with integrating {topic} with existing systems?",
        "What are the latest advancements in {topic} that you find most promising?",
        "How do you optimize costs when using {topic} at scale?",
        "What monitoring and observability practices do you recommend for {topic}?",
        "How do you handle failure scenarios with {topic} in production?",
        "What are the most useful patterns for implementing {topic} with CI/CD pipelines?"
    ]
    
    sdk_templates = [
        "What features would you like to see added to the {topic}?",
        "How do you handle authentication best practices when using the {topic}?",
        "What are the most common pitfalls when using the {topic} and how do you avoid them?",
        "How do you effectively test applications built with the {topic}?",
        "What performance optimizations have you implemented when working with the {topic}?",
        "How do you manage dependency versioning when using the {topic}?",
        "What's your approach to error handling with the {topic}?",
        "How do you implement logging and telemetry with the {topic}?",
        "What tools or frameworks do you use alongside the {topic} to improve productivity?"
    ]
    
    general_templates = [
        "What are your thoughts on the current state of {topic}?",
        "How can {topic} be improved?",
        "What challenges have you faced with {topic}?",
        "Do you have any success stories related to {topic}?",
        "What resources would you recommend for someone getting started with {topic}?",
        "How do you see {topic} evolving in the next year?",
        "What alternatives to {topic} have you explored?",
        "What metrics do you use to measure success with {topic}?",
        "How has {topic} changed your workflow or development process?"
    ]
    
    # Map specific tags to template categories
    for tag in tags:
        tag_name = tag["name"]
        tag_desc = tag.get("description", "")
        
        # Skip non-discussion tags
        if tag_name in ["duplicate", "invalid", "wontfix"]:
            continue
        
        # Choose appropriate templates based on tag name
        if any(keyword in tag_name for keyword in ["ai-", "openai", "search", "semantic"]):
            templates = azure_ai_templates
        elif "sdk" in tag_name:
            templates = sdk_templates
        else:
            templates = general_templates
            
        # Generate questions
        tag_questions = []
        topic = tag_name.replace("-", " ").title()
        
        # Use description to enhance the topic if available
        if tag_desc and "Discussions related to" in tag_desc:
            topic = tag_desc.replace("Discussions related to ", "").strip(".")
        
        # Select random templates for this tag
        selected_templates = random.sample(templates, min(num_questions_per_tag, len(templates)))
        
        for template in selected_templates:
            question = template.format(topic=topic)
            tag_questions.append(question)
            
        questions[tag_name] = tag_questions
    
    return questions

def format_output(questions_by_tag):
    """Format the questions in a readable way."""
    output = "# Discussion Questions by Tag\n\n"
    
    for tag, questions in questions_by_tag.items():
        output += f"## {tag}\n\n"
        for i, question in enumerate(questions, 1):
            output += f"{i}. {question}\n"
        output += "\n"
    
    return output

def save_discussion_questions(questions, filename="discussion_questions.md"):
    """Save the generated questions to a markdown file."""
    output = format_output(questions)
    output_path = Path(__file__).parent / filename
    output_path.write_text(output)
    print(f"Generated discussion questions saved to {filename}")
    return output

if __name__ == "__main__":
    tags = load_tags()
    questions = generate_discussion_questions(tags, num_questions_per_tag=3)
    save_discussion_questions(questions)
    
    # Print a sample of the questions
    print("\n=== Sample Discussion Questions ===\n")
    sample_tags = random.sample(list(questions.keys()), min(5, len(questions)))
    for tag in sample_tags:
        print(f"{tag}:")
        for question in questions[tag]:
            print(f"  - {question}")
        print()