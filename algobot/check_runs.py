from typing import Any

from gidgethub import aiohttp as gh_aiohttp
from gidgethub import routing, sansio

from . import utils

router = routing.Router()

FAILURE_LABEL = "Status: Tests are failing"


@router.register("check_run", action="completed")
async def check_run_completed(
    event: sansio.Event,
    gh: gh_aiohttp.GitHubAPI,
    *args: Any,
    **kwargs: Any,
) -> None:
    """Handler for check run completed event.

    We will get the event payload everytime a check run is completed which is
    a lot of times for a single commit. So, the `if` statement makes sure we
    execute the block only when the last check run is completed.
    """
    commit_sha = event.data["check_run"]["head_sha"]
    installation_id = event.data["installation"]["id"]
    repository = event.data["repository"]["full_name"]

    pr_for_commit = await utils.get_pr_for_commit(
        commit_sha, gh, installation_id, repository
    )
    # The hook came from a check run not made in any pull request
    if not pr_for_commit:
        print(
            f"This commit is not from a PR: "
            f"https://api.github.com/repos/{repository}/commits/{commit_sha}"
        )
        return None

    check_runs = await utils.get_check_runs_for_commit(
        commit_sha, gh, installation_id, repository
    )

    all_check_run_status = [
        check_run["status"] for check_run in check_runs["check_runs"]
    ]
    all_check_run_conclusions = [
        check_run["conclusion"] for check_run in check_runs["check_runs"]
    ]

    if (
        "in_progress" not in all_check_run_status
        and "queued" not in all_check_run_status
    ):  # wait until all check runs are completed
        pr_number = pr_for_commit["number"]
        pr_labels = [label["name"] for label in pr_for_commit["labels"]]
        if any(
            element in [None, "failure", "timed_out"]
            for element in all_check_run_conclusions
        ):
            print(f"Failure detected in PR: {pr_number}")
            # Add the failure label only if it doesn't exist
            if FAILURE_LABEL not in pr_labels:
                await utils.add_label_to_pr(
                    FAILURE_LABEL, pr_number, gh, installation_id, repository
                )
        # Check run is successful so if the label exist, remove it
        elif FAILURE_LABEL in pr_labels:
            await utils.remove_label_from_pr(
                FAILURE_LABEL, pr_number, gh, installation_id, repository
            )
