from pathlib import Path
from lib.config.prompts import Prompts
from langchain import LLMChain
from langchain.chat_models import ChatOpenAI
from loguru import logger
from lib.sql import SuperAgent, TaskListItem, Goal
from sqlalchemy.orm import Session
import re


class TaskPrioritizationAgent:
    """Chain to prioritize tasks."""

    def __init__(self, super_agent: SuperAgent, session: Session, config: Path):
        self.super_agent = super_agent
        self.session = session
        goals = Goal.get_goals(session=session, agent=super_agent)
        prompts = Prompts(config=config)
        self.objective = Goal.get_prompt(goals=goals, prompts=prompts)
        prompt, llm = prompts.get_task_prioritization_prompt()
        self.chain = LLMChain(
            prompt=prompt, llm=llm, verbose=True
        )

    async def arun(
        self,
        task_list_item: TaskListItem,
    ) -> None:
        """Prioritize the given task list item."""
        other_tasks = TaskListItem.get_random_task_list_item(agent=self.super_agent, session=self.session)
        if task_list_item in other_tasks:
            other_tasks.remove(task_list_item)
        other_tasks_table = TaskListItem.task_list_to_table(other_tasks)

        out = await self.chain.arun(
            objective=self.objective, task_description=task_list_item.description, other_tasks_table=other_tasks_table
        )

        # Find the final float in the output string using regex
        priority_list = re.findall(r"[-+]?\d*\.\d+|\d+", out)
        if len(priority_list) == 0:
            logger.error("No priority found in output string.")
        else:
            try:
                priority = float(priority_list[-1])
            except ValueError:
                logger.error(f"Could not convert priority {priority_list[-1]} to float.")
            else:
                task_list_item.priority = priority

        return None