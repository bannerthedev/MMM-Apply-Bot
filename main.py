import asyncio
import os
import dotenv
dotenv.load_dotenv()

import discord
from discord.ext import commands
from discord.ui import View, Select, Button
from discord import app_commands, TextChannel

# ============== CONFIG ==============
GUILD_IDS = 1338455645896310784  # or None to register globally
APPLICATION_CHANNEL_ID = 1509686940512030870
TRANSACTIONS_CHANNEL_ID = 1506741709445271766

CASTER_ROLE_ID = 1338478126354923530
REF_ROLE_ID = 1356887381156036688
COMMENTATOR_ROLE_ID = 1346047919874248748
HELPER_ROLE_ID = 1505268458135486544

STAFF_ROLE_ID = 111111111111111111  # replace if used

APP_STATUS = {
    "caster": True,
    "ref": True,
    "commentator": True,
    "staff": True,
    "team": True,
}
# ======================================

intents = discord.Intents.default()
intents.messages = True
intents.dm_messages = True
intents.guilds = True
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# In-memory tracking of panel message IDs per guild: {guild_id: [ (channel_id, message_id), ... ]}
PANEL_MESSAGES = {}

# ---------- Register UI ----------
class RegisterSelect(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RegisterTypeSelect())

class RegisterTypeSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Caster", value="caster", description="Apply to be a caster"),
            discord.SelectOption(label="Referee", value="ref", description="Apply to be a referee"),
            discord.SelectOption(label="Commentator", value="commentator", description="Apply to be a commentator"),
            discord.SelectOption(label="Staff", value="staff", description="Apply to be staff"),
            discord.SelectOption(label="Team", value="team", description="Apply as a team"),
        ]
        super().__init__(placeholder="Choose application type", min_values=1, max_values=1, options=options, custom_id="register_select")

    async def callback(self, interaction: discord.Interaction):
        app_type = self.values[0]
        # Block team apps for staff role if set
        if app_type == "team" and isinstance(interaction.user, discord.Member):
            if any(r.id == STAFF_ROLE_ID for r in interaction.user.roles):
                await interaction.response.send_message("You already have a staff role and cannot apply for a team.", ephemeral=True)
                return
        # check open/closed
        if not APP_STATUS.get(app_type, True):
            await interaction.response.send_message("This App has been closed by an admin", ephemeral=True)
            return
        await interaction.response.send_message("Application Started — check your DMs.", ephemeral=True)
        await start_application_flow(interaction.user, app_type, interaction)

# ---------- Application flow with intro Accept/Deny ----------
async def start_application_flow(user: discord.User, app_type: str, interaction: discord.Interaction):
    # DM intro
    try:
        dm = await user.create_dm()
    except Exception:
        try:
            await interaction.followup.send("I couldn't DM you. Please enable DMs from server members and try again.", ephemeral=True)
        except: pass
        return

    class IntroView(View):
        def __init__(self):
            super().__init__(timeout=300)
            self.choice = None

        @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, custom_id="intro_accept")
        async def accept(self, button_interaction: discord.Interaction, button: Button):
            if button_interaction.user.id != user.id:
                await button_interaction.response.send_message("This is not for you.", ephemeral=True)
                return
            self.choice = "accept"
            await button_interaction.response.edit_message(content="You accepted. Starting application...", view=None)
            self.stop()

        @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger, custom_id="intro_deny")
        async def deny(self, button_interaction: discord.Interaction, button: Button):
            if button_interaction.user.id != user.id:
                await button_interaction.response.send_message("This is not for you.", ephemeral=True)
                return
            self.choice = "deny"
            await button_interaction.response.edit_message(content="You declined the application. If you change your mind, re-run /register.", view=None)
            self.stop()

    intro_view = IntroView()
    try:
        await dm.send(
            "Application Started\nPlease answer the questions below, either by selecting menu options or by sending messages to the bot.",
            view=intro_view
        )
    except Exception:
        try:
            await interaction.followup.send("I couldn't send the intro DM. Please enable DMs from server members and try again.", ephemeral=True)
        except: pass
        return

    await intro_view.wait()
    if intro_view.choice is None:
        try:
            await dm.send("Timed out. Please re-run apply to start again.")
        except: pass
        return
    if intro_view.choice == "deny":
        return

    async def collect_text(question: str):
        await dm.send(question)
        def check(m: discord.Message):
            return m.author.id == user.id and isinstance(m.channel, discord.DMChannel)
        try:
            msg = await bot.wait_for('message', timeout=300.0, check=check)
        except asyncio.TimeoutError:
            await dm.send("Timed out. Please re-run apply to start again.")
            return None
        content = msg.content.strip()
        if not content:
            await dm.send("Response cannot be empty. Please re-run apply to start again.")
            return None
        return content

    async def ask_yes_no(question: str):
        class YesNoView(View):
            def __init__(self):
                super().__init__(timeout=300)
                self.value = None

            @discord.ui.select(placeholder="Select Yes or No", min_values=1, max_values=1, options=[
                discord.SelectOption(label="Yes", value="yes"),
                discord.SelectOption(label="No", value="no")
            ])
            async def select_callback(self, interaction2: discord.Interaction, select: Select):
                if interaction2.user.id != user.id:
                    await interaction2.response.send_message("This is not for you.", ephemeral=True)
                    return
                self.value = select.values[0]
                await interaction2.response.edit_message(content=f"{question}\nAnswer: {self.value}", view=None)
                self.stop()

        view = YesNoView()
        msg = await dm.send(question, view=view)
        await view.wait()
        if view.value is None:
            try:
                await msg.edit(content="Timed out. Please re-run apply to start again.", view=None)
            except: pass
            return None
        return view.value

    answers = {}

    # Questions per app_type
    if app_type == "caster":
        answers["1"] = await collect_text("1/10. What is your Discord username & ID?"); 
        if answers["1"] is None: return
        answers["2"] = await ask_yes_no("2/10. Do you have a mic?"); 
        if answers["2"] is None: return
        answers["3"] = await collect_text("3/10. Do you have any past experience with casting in Gorilla Tag? If so please explain."); 
        if answers["3"] is None: return
        answers["4"] = await collect_text("4/10. Why do you want to become a Caster for MMM?"); 
        if answers["4"] is None: return
        answers["5"] = await collect_text("5/10. What is your Upload & Download Speed? (use https://www.speedtest.net/)"); 
        if answers["5"] is None: return
        answers["6"] = await collect_text("6/10. List your PC specifications."); 
        if answers["6"] is None: return
        answers["7"] = await collect_text("7/10. If you have past casting experience, link your YouTube/Twitch/etc."); 
        if answers["7"] is None: return
        answers["8"] = await collect_text("8/10. Are you familiar with OBS?"); 
        if answers["8"] is None: return
        answers["9"] = await collect_text("9/10. Please send a video showing OBS tasks (make Game Capture, add mic, import/export profile, make scene). Upload via Drive/MediaFire and send link."); 
        if answers["9"] is None: return
        answers["10"] = await collect_text("10/10. Any questions?"); 
        if answers["10"] is None: return

    elif app_type == "ref":
        answers["1"] = await collect_text("1/11. What is your Discord username & ID?"); 
        if answers["1"] is None: return
        answers["2"] = await collect_text("2/11. Name 3 official scrims you have reffed for (include teams and score)."); 
        if answers["2"] is None: return
        answers["3"] = await collect_text("3/11. What is the recommended minimum time a ref should give late players?"); 
        if answers["3"] is None: return
        answers["4"] = await collect_text("4/11. How long do runners have before taggers can pursue them?"); 
        if answers["4"] is None: return
        answers["5"] = await collect_text("5/11. Where do runners go when tagged by the opposing team?"); 
        if answers["5"] is None: return
        answers["6"] = await collect_text("6/11. What headsets are allowed in MMM official scrims?"); 
        if answers["6"] is None: return
        answers["7"] = await collect_text("7/11. Can teams have different colors than there teammates? If not, why?"); 
        if answers["7"] is None: return
        answers["8"] = await collect_text("8/11. Do players have team abbreviation in their name while playing? If not, why?"); 
        if answers["8"] is None: return
        answers["9"] = await ask_yes_no("9/11. Do you understand that if you don't ref at least 3-5 matches per season you may be removed/demoted?"); 
        if answers["9"] is None: return
        answers["10"] = await ask_yes_no("10/11. Do you understand that if you are caught being bias you WILL be removed?"); 
        if answers["10"] is None: return
        answers["11"] = await ask_yes_no("11/11. Do you understand you must follow your Head Referees instructions at all times?"); 
        if answers["11"] is None: return

    elif app_type == "commentator":
        answers["1"] = await collect_text("1/5. What is your Discord username?"); 
        if answers["1"] is None: return
        answers["2"] = await collect_text("2/5. Do you know in-game callouts and how the league rules work?"); 
        if answers["2"] is None: return
        answers["3"] = await collect_text("3/5. Do you have experience commentating? If so list the discords you have been a commentator for."); 
        if answers["3"] is None: return
        answers["4"] = await collect_text("4/5. Why should you be commentator? Please give a thorough reasoning on why."); 
        if answers["4"] is None: return
        answers["5"] = await collect_text("5/5. If you use a PC to call on discord what microphone do you use?"); 
        if answers["5"] is None: return

    elif app_type == "staff":
        answers["1"] = await collect_text("1/4. What Is Your Username And ID."); 
        if answers["1"] is None: return
        answers["2"] = await collect_text("2/4. What Is Your Age."); 
        if answers["2"] is None: return
        answers["3"] = await collect_text("3/4. Do you have experience being a moderator for a league? If yes, please list the league and when you served."); 
        if answers["3"] is None: return
        answers["4"] = await collect_text("4/4. Why Should We Accept You."); 
        if answers["4"] is None: return

    elif app_type == "team":
        answers["1"] = await collect_text("1/5. Team name and abbreviation")
        if answers["1"] is None: return
        answers["2"] = await collect_text("2/5. Hex color code")
        if answers["2"] is None: return
        answers["3"] = await collect_text("3/5. Roster")
        if answers["3"] is None: return
        answers["4"] = await collect_text("4/5. Server (if private do not type)")
        if answers["4"] is None: return
        answers["5"] = await ask_yes_no("5/5. yk if you are accepted you need to make a ticket and send your pfp")
        if answers["5"] is None: return

    await dm.send("Application submitted.\nYour application has been submitted.")

    # Build embed
    embed = discord.Embed(title=f"{user.display_name}'s {app_type.capitalize()} Application", description="Application Submitted", color=0x2F3136)
    try:
        embed.set_thumbnail(url=user.display_avatar.url)
    except: pass
    for qnum, ans in answers.items():
        embed.add_field(name=f"Q{qnum}", value=ans if len(ans) < 1024 else ans[:1021] + "...", inline=False)
    embed.set_footer(text=f"User ID: {user.id}")

    # Staff decision view (anonymized public messages)
    class StaffDecisionView(View):
        def __init__(self, target_user_id: int, app_type: str, answers_dict: dict):
            super().__init__(timeout=None)
            self.target_user_id = target_user_id
            self.app_type = app_type
            self.answers = answers_dict

        @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, custom_id="app_accept")
        async def accept(self, interaction2: discord.Interaction, button: Button):
            staff_member = interaction2.user
            if not isinstance(staff_member, discord.Member) or not staff_member.guild_permissions.administrator:
                await interaction2.response.send_message("You don't have permission to use this.", ephemeral=True)
                return

            # Public edit without revealing staff member
            try:
                await interaction2.response.edit_message(content="Application accepted.", embed=interaction2.message.embeds[0], view=None)
            except:
                try:
                    await interaction2.message.edit(content="Application accepted.", view=None)
                except: pass

            # DM applicant (anonymous)
            try:
                applicant = await bot.fetch_user(self.target_user_id)
                await applicant.send("Your application was accepted.")
            except: pass

            # give role if applicable
            try:
                guild = interaction2.guild or (await bot.fetch_guild(GUILD_IDS) if isinstance(GUILD_IDS, int) else None)
                if guild:
                    role_id = None
                    if self.app_type == "caster":
                        role_id = CASTER_ROLE_ID
                    elif self.app_type in ("ref", "referee"):
                        role_id = REF_ROLE_ID
                    elif self.app_type == "commentator":
                        role_id = COMMENTATOR_ROLE_ID
                    elif self.app_type == "staff":
                        role_id = HELPER_ROLE_ID

                    if role_id:
                        role = guild.get_role(role_id) or await guild.fetch_role(role_id)
                        if role:
                            try:
                                member = await guild.fetch_member(self.target_user_id)
                                await member.add_roles(role, reason="Application accepted")
                            except discord.NotFound:
                                pass
                            except: pass
            except: pass

            # TEAM: send /create-team line then delete
            if self.app_type == "team":
                try:
                    chan = bot.get_channel(TRANSACTIONS_CHANNEL_ID) or await bot.fetch_channel(TRANSACTIONS_CHANNEL_ID)
                    team_name = self.answers.get("1", "Unknown Team")
                    raw_color = self.answers.get("2", "").strip()
                    color = raw_color.lstrip("#")
                    if len(color) != 6 or any(c not in "0123456789abcdefABCDEF" for c in color):
                        try:
                            await interaction2.followup.send(
                                f"Did not send team creation: hex color `{raw_color}` is invalid (must be 6 hex digits).",
                                ephemeral=True
                            )
                        except:
                            pass
                        return
                    captain_mention = f"<@{self.target_user_id}>"
                    team_command = f'/create-team "{team_name}" {captain_mention} {color}'
                    msg = await chan.send(team_command)
                    try:
                        await msg.delete()
                    except:
                        pass
                except:
                    pass

        @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="app_deny")
        async def deny(self, interaction2: discord.Interaction, button: Button):
            staff_member = interaction2.user
            if not isinstance(staff_member, discord.Member) or not staff_member.guild_permissions.administrator:
                await interaction2.response.send_message("You don't have permission to use this.", ephemeral=True)
                return

            # Public edit without revealing staff member
            try:
                await interaction2.response.edit_message(content="Application denied.", embed=interaction2.message.embeds[0], view=None)
            except:
                try:
                    await interaction2.message.edit(content="Application denied.", view=None)
                except: pass

            # DM applicant (anonymous)
            try:
                u = await bot.fetch_user(self.target_user_id)
                await u.send("Your application was denied.")
            except:
                pass

    try:
        app_channel = bot.get_channel(APPLICATION_CHANNEL_ID) or await bot.fetch_channel(APPLICATION_CHANNEL_ID)
        view = StaffDecisionView(user.id, app_type, answers)
        await app_channel.send(embed=embed, view=view)
        await dm.send("Your application has been sent to staff.")
    except Exception:
        await dm.send("Error: application channel not configured or bot lacks permission to post. Contact an admin.")
        return

# ---------- Applications Panel ----------
class ApplicationsPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _start_if_open(self, interaction: discord.Interaction, key: str, user_friendly: str):
        if not APP_STATUS.get(key, True):
            await interaction.response.send_message(f"{user_friendly} applications are currently closed.", ephemeral=True)
            return
        await interaction.response.send_message(f"Starting {user_friendly} application — check your DMs.", ephemeral=True)
        await start_application_flow(interaction.user, key, interaction)

    @discord.ui.button(custom_id="panel_ref", label="Referee Applications", style=discord.ButtonStyle.primary)
    async def ref_button(self, interaction: discord.Interaction, button: Button):
        await self._start_if_open(interaction, "ref", "Referee")

    @discord.ui.button(custom_id="panel_commentator", label="Commentator Applications", style=discord.ButtonStyle.primary)
    async def commentator_button(self, interaction: discord.Interaction, button: Button):
        await self._start_if_open(interaction, "commentator", "Commentator")

    @discord.ui.button(custom_id="panel_caster", label="Caster Applications", style=discord.ButtonStyle.primary)
    async def caster_button(self, interaction: discord.Interaction, button: Button):
        await self._start_if_open(interaction, "caster", "Caster")

    @discord.ui.button(custom_id="panel_staff", label="Staff Applications", style=discord.ButtonStyle.primary)
    async def staff_button(self, interaction: discord.Interaction, button: Button):
        await self._start_if_open(interaction, "staff", "Staff")

def build_panel_content():
    def status_text(key):
        return " (Closed)" if not APP_STATUS.get(key, True) else ""
    content = (
        "# 📝Applications 📝 #\n"
        "Welcome to Monke Monke Monke League. We are currently looking for active refs, casters, commentators, and staff members. If you would like to be apart of are team please apply with are provide sources.\n\n"
        f"● **Ref application**{status_text('ref')}\n"
        f"● **Commentator application**{status_text('commentator')}\n"
        f"● **Caster application**{status_text('caster')}\n"
        f"● **Staff application**{status_text('staff')}\n\n"
        "We really appreciate yall taking your time out of your day to apply and to try to be apart of are team. This means a lot to the MMM boards and staff for helping us through the scrims and server. We hope you enjoy your time here and thank you for applying.\n\n"
        "Your fellow\nBoards of MMM"
    )
    return content

# ---------- on_ready & slash registration ----------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        tree = bot.tree
        guild_obj = discord.Object(id=GUILD_IDS) if isinstance(GUILD_IDS, int) else None

        # /register
        @tree.command(name="register", description="Start an application (Caster / Ref / Commentator / Staff / Team)", guild=guild_obj)
        async def register_command(interaction: discord.Interaction):
            guild_id = interaction.guild.id if interaction.guild else None
            if guild_id and PANEL_MESSAGES.get(guild_id):
                ch_id, msg_id = PANEL_MESSAGES[guild_id][0]
                try:
                    ch = interaction.guild.get_channel(ch_id) or await interaction.guild.fetch_channel(ch_id)
                    await ch.fetch_message(msg_id)
                    await interaction.response.send_message(f"A panel has already been made — please go apply here <#{ch_id}>", ephemeral=True)
                    return
                except Exception:
                    PANEL_MESSAGES[guild_id].pop(0)
                    if not PANEL_MESSAGES[guild_id]:
                        PANEL_MESSAGES.pop(guild_id, None)

            view = RegisterSelect()
            await interaction.response.send_message("Select application type:", view=view, ephemeral=True)

        # /manage
        @tree.command(name="manage", description="Open or close an application type", guild=guild_obj)
        @app_commands.describe(action="open or close", app="application type to manage")
        @app_commands.choices(action=[
            app_commands.Choice(name="open", value="open"),
            app_commands.Choice(name="close", value="close"),
        ], app=[
            app_commands.Choice(name="caster", value="caster"),
            app_commands.Choice(name="ref", value="ref"),
            app_commands.Choice(name="commentator", value="commentator"),
            app_commands.Choice(name="staff", value="staff"),
            app_commands.Choice(name="team", value="team"),
        ])
        async def manage_command(interaction: discord.Interaction, action: app_commands.Choice[str], app: app_commands.Choice[str]):
            member = interaction.user
            if not isinstance(member, discord.Member) or not member.guild_permissions.administrator:
                await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
                return

            app_key = app.value
            if action.value == "close":
                APP_STATUS[app_key] = False
                await interaction.response.send_message(f"{app_key.capitalize()} application closed.\n\nThis app has been closed by an admin", ephemeral=True)
            else:
                APP_STATUS[app_key] = True
                await interaction.response.send_message(f"{app_key.capitalize()} application opened.", ephemeral=True)

            guild_id = interaction.guild.id if interaction.guild else None
            if not guild_id:
                return

            entries = PANEL_MESSAGES.get(guild_id, [])
            if not entries:
                return

            content = build_panel_content()
            view = ApplicationsPanelView()
            for child in view.children:
                cid = getattr(child, "custom_id", None)
                if cid == "panel_ref":
                    child.disabled = not APP_STATUS.get("ref", True)
                elif cid == "panel_commentator":
                    child.disabled = not APP_STATUS.get("commentator", True)
                elif cid == "panel_caster":
                    child.disabled = not APP_STATUS.get("caster", True)
                elif cid == "panel_staff":
                    child.disabled = not APP_STATUS.get("staff", True)

            valid_entries = []
            for ch_id, msg_id in list(entries):
                try:
                    ch = interaction.guild.get_channel(ch_id) or await interaction.guild.fetch_channel(ch_id)
                    msg = await ch.fetch_message(msg_id)
                    await msg.edit(content=content, view=view)
                    valid_entries.append((ch_id, msg_id))
                except Exception:
                    continue

            if valid_entries:
                PANEL_MESSAGES[guild_id] = valid_entries
            else:
                PANEL_MESSAGES.pop(guild_id, None)

        # /panel - single message containing content + buttons
        @tree.command(name="panel", description="Post the applications panel (admins only)", guild=guild_obj)
        @app_commands.describe(channel="Channel to post the applications panel in")
        async def panel_command(interaction: discord.Interaction, channel: TextChannel):
            member = interaction.user
            if not isinstance(member, discord.Member) or not member.guild_permissions.administrator:
                await interaction.response.send_message("You must be an administrator to use this command.", ephemeral=True)
                return

            content = build_panel_content()
            view = ApplicationsPanelView()
            for child in view.children:
                cid = getattr(child, "custom_id", None)
                if cid == "panel_ref":
                    child.disabled = not APP_STATUS.get("ref", True)
                elif cid == "panel_commentator":
                    child.disabled = not APP_STATUS.get("commentator", True)
                elif cid == "panel_caster":
                    child.disabled = not APP_STATUS.get("caster", True)
                elif cid == "panel_staff":
                    child.disabled = not APP_STATUS.get("staff", True)

            try:
                msg = await channel.send(content, view=view)
                guild_id = interaction.guild.id if interaction.guild else None
                if guild_id:
                    PANEL_MESSAGES.setdefault(guild_id, []).append((channel.id, msg.id))
                await interaction.response.send_message(f"Panel posted in {channel.mention}.", ephemeral=True)
            except Exception:
                await interaction.response.send_message("Failed to post panel. Make sure I have permission to send messages and manage messages in that channel.", ephemeral=True)

        if guild_obj:
            await tree.sync(guild=guild_obj)
        else:
            await tree.sync()
        print("Slash commands registered.")
    except Exception as e:
        print("Failed to register command:", e)

# Start the bot
bot.run(os.getenv("BOT_TOKEN"))

