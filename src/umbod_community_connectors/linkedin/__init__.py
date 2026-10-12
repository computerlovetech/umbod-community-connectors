"""LinkedIn operations are individually permissionable in Umbod."""

from typing import Annotated, Literal

from pydantic import Field
from umbod_sdk.connectors.plugin_api import Connector

from .admin_configuration import LinkedInConfiguration
from .api_client import LinkedInClient
from .configuration_check import check_configuration

connector = Connector(
    id="linkedin",
    name="LinkedIn",
    configuration=LinkedInConfiguration,
    description="Community LinkedIn connector inspired by Mark Ruvald's linkedin-rs.",
    capability_description=(
        "Read profiles, feed, conversations, connections and notifications; "
        "publish posts, react, comment, message and manage invitations."
    ),
)
connector.configuration_check(check_configuration)
Start = Annotated[int, Field(ge=0, description="Zero-based result offset.")]
Count = Annotated[int, Field(ge=1, description="Number of results in this page.")]
Text = Annotated[str, Field(min_length=1, description="Plain text content.")]
Profile = Annotated[
    str, Field(min_length=1, description="LinkedIn public profile slug, such as jane-doe.")
]
Recipient = Annotated[
    str,
    Field(min_length=1, description="Public profile slug or LinkedIn member/profile URN."),
]
Post = Annotated[str, Field(min_length=1, description="LinkedIn post URN or numeric activity ID.")]
Cursor = Annotated[
    int | None, Field(ge=0, description="Epoch milliseconds cursor; omit for first page.")
]
Reaction = Annotated[
    Literal[
        "LIKE", "PRAISE", "EMPATHY", "INTEREST", "APPRECIATION", "ENTERTAINMENT", "CELEBRATION"
    ],
    Field(description="Reaction type to add or remove."),
]


@connector.tool(
    description="Check the configured LinkedIn session using the account profile endpoint."
)
def auth_status(configuration: LinkedInConfiguration):
    result = check_configuration(configuration)
    return {"valid": result.valid, "message": result.message}


@connector.tool(description="Read the authenticated LinkedIn member's profile.")
def profile_me(configuration: LinkedInConfiguration):
    with LinkedInClient(configuration) as client:
        return client.me()


@connector.tool(
    description="Read a profile using its public slug, without the explicit visit operation."
)
def profile_view(public_id: Profile, configuration: LinkedInConfiguration):
    with LinkedInClient(configuration) as client:
        return client.profile(public_id)


@connector.tool(
    description="Visit a profile. This registers a profile view visible to that member."
)
def profile_visit(public_id: Profile, configuration: LinkedInConfiguration):
    with LinkedInClient(configuration) as client:
        return client.profile(public_id, visit=True)


@connector.tool(description="Read who viewed your LinkedIn profile.")
def profile_viewers(configuration: LinkedInConfiguration):
    with LinkedInClient(configuration) as client:
        return client.get("identity/wvmpCards")


@connector.tool(description="Read a page of LinkedIn feed updates.")
def feed_list(configuration: LinkedInConfiguration, start: Start = 0, count: Count = 20):
    with LinkedInClient(configuration) as client:
        return client.feed(start, count)


@connector.tool(
    description="Add a reaction to a LinkedIn post. This changes your account's reaction."
)
def feed_react(post: Post, configuration: LinkedInConfiguration, reaction: Reaction = "LIKE"):
    with LinkedInClient(configuration) as client:
        return client.reaction(post, reaction)


@connector.tool(description="Remove your reaction from a LinkedIn post.")
def feed_unreact(post: Post, configuration: LinkedInConfiguration, reaction: Reaction = "LIKE"):
    with LinkedInClient(configuration) as client:
        return client.reaction(post, reaction, remove=True)


@connector.tool(description="Publish a comment on a LinkedIn post.")
def feed_comment(post: Post, text: Text, configuration: LinkedInConfiguration):
    with LinkedInClient(configuration) as client:
        return client.comment(post, text)


@connector.tool(description="Publish a text post to LinkedIn, publicly or to connections only.")
def feed_post(
    text: Text,
    configuration: LinkedInConfiguration,
    visibility: Annotated[
        Literal["ANYONE", "CONNECTIONS_ONLY"], Field(description="Post audience.")
    ] = "ANYONE",
):
    with LinkedInClient(configuration) as client:
        return client.create_post(text, visibility)


@connector.tool(description="Read a page of your LinkedIn connections, most recently added first.")
def connections_list(configuration: LinkedInConfiguration, start: Start = 0, count: Count = 50):
    with LinkedInClient(configuration) as client:
        return client.connections(start, count)


@connector.tool(description="Send a LinkedIn connection invitation, optionally with a message.")
def connections_invite(
    recipient: Recipient,
    configuration: LinkedInConfiguration,
    message: Annotated[str | None, Field(description="Optional invitation message.")] = None,
):
    with LinkedInClient(configuration) as client:
        return client.invite(recipient, message)


@connector.tool(
    description="Read pending received connection invitations, including acceptance identifiers."
)
def connections_invitations(
    configuration: LinkedInConfiguration, start: Start = 0, count: Count = 20
):
    with LinkedInClient(configuration) as client:
        return client.query("invitations", f"(start:{start},count:{count},includeInsights:true)")


@connector.tool(description="Accept a received LinkedIn connection invitation.")
def connections_accept(
    invitation: Annotated[
        str, Field(min_length=1, description="Invitation ID or URN returned by invitations.")
    ],
    shared_secret: Annotated[
        str, Field(min_length=1, description="Invitation sharedSecret returned by invitations.")
    ],
    configuration: LinkedInConfiguration,
):
    with LinkedInClient(configuration) as client:
        return client.accept(invitation, shared_secret)


@connector.tool(description="Search LinkedIn people by keywords with pagination.")
def search_people(
    keywords: Text, configuration: LinkedInConfiguration, start: Start = 0, count: Count = 20
):
    with LinkedInClient(configuration) as client:
        return client.search("people", keywords, start, count)


@connector.tool(description="Search LinkedIn jobs by keywords with pagination.")
def search_jobs(
    keywords: Text, configuration: LinkedInConfiguration, start: Start = 0, count: Count = 20
):
    with LinkedInClient(configuration) as client:
        return client.search("jobs", keywords, start, count)


@connector.tool(
    description="Read messaging conversations; use last activity timestamps for pagination."
)
def messages_list(configuration: LinkedInConfiguration, count: Count = 20, before: Cursor = None):
    with LinkedInClient(configuration) as client:
        return client.conversations(count, before)


@connector.tool(
    description="Read messages in a LinkedIn conversation, optionally before a timestamp."
)
def messages_read(
    conversation: Annotated[
        str, Field(min_length=1, description="Conversation URN or messaging thread ID.")
    ],
    configuration: LinkedInConfiguration,
    before: Cursor = None,
):
    with LinkedInClient(configuration) as client:
        return client.messages(conversation, before)


@connector.tool(description="Send a LinkedIn direct message to a member.")
def messages_send(recipient: Recipient, text: Text, configuration: LinkedInConfiguration):
    with LinkedInClient(configuration) as client:
        return client.send_message(recipient, text)


@connector.tool(description="Read a page of LinkedIn notifications.")
def notifications_list(configuration: LinkedInConfiguration, start: Start = 0, count: Count = 20):
    with LinkedInClient(configuration) as client:
        return client.query("notifications", f"(start:{start},count:{count})")
