import asyncio
import discord
from discord.ext import commands
from discord.ui import View, Select, Button
import os
from dotenv import load_dotenv

load_dotenv()

# ================ CONFIG =================
GUILD_IDS = 1338455645896310784       # main guild where commands live
APPLICATION_CHANNEL_ID = 1509686940512030870  # channel where apps are posted
TRANSACTIONS_CHANNEL_ID = 1506741709445271766  # channel MMM League Manager listens in

# Role IDs to give on acceptance
CASTER_ROLE_ID = 1338478126354923530
REF_ROLE_ID = 1356887381156036688
COMMENTATOR_ROLE_ID = 1346047919874248748
HELPER_ROLE_ID = 1505268458135486544  # set to your helper role ID

# Staff role IDs (if user has any of these, treat as staff and block team app)
STAFF_ROLE_IDS = [
    1351639240861028447,
    1374305296326856734,
    1339202997208616990,
    1353119096211898450,
    1472041769049784330,
    1338475990833303677,
]

# App open/closed status
APP_STATUS = {
    "caster": True,
    "ref": True,
    "commentator": True,
    "staff": True,
    "team": True,
}
# =========================================

intents = discord.Intents.default()
intents.messages = True
intents.dm_messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- /register UI ----------
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
        super().__init__(
            placeholder="Choose application type",
            min_values=1, max_values=1,
            options=options, custom_id="register_select"
        )

    async def callback(self, interaction: discord.Interaction):
        app_type = self.values[0]
        # Block team apps for users with staff roles
        if app_type == "team" and isinstance(interaction.user, discord.Member):
            user_role_ids = {r.id for r in interaction.user.roles}
            if any(sid in user_role_ids for sid in STAFF_ROLE_IDS):
                await interaction.response.send_message("You already have a staff role and cannot apply for a team.", ephemeral=True)
                return
        if not APP_STATUS.get(app_type, True):
            await interaction.response.send_message("This App has been closed by a admin", ephemeral=True)
            return
        await interaction.response.send_message("Application Started — check your DMs.", ephemeral=True)
        await start_application_flow(interaction.user, app_type, interaction)

# ---------- Application flow ----------
async def start_application_flow(user: discord.User, app_type: str, interaction: discord.Interaction):
    try:
        dm = await user.create_dm()
        await dm.send("Application Started\nPlease answer the questions below, either by selecting menu options or by sending messages to the bot.")
    except Exception:
        try:
            await interaction.followup.send("I couldn't DM you. Please enable DMs from server members and try again.", ephemeral=True)
        except: pass
        return

    async def collect_text(question: str):
        await dm.send(question)
        def check(m: discord.Message):
            return m.author.id == user.id and isinstance(m.channel, discord.DMChannel)
        try:
            msg = await bot.wait_for('message', timeout=300.0, check=check)
        except asyncio.TimeoutError:
            await dm.send("Timed out. Please re-run /register to start again.")
            return None
        content = msg.content.strip()
        if not content:
            await dm.send("Response cannot be empty. Please re-run /register.")
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
                await msg.edit(content="Timed out. Please re-run /register to start again.", view=None)
            except: pass
            return None
        return view.value

    answers = {}

    # QUESTIONS
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
        answers["1"] = await collect_text("1/4. What is your Username and ID."); 
        if answers["1"] is None: return
        answers["2"] = await collect_text("2/4. What is your age."); 
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
    embed.set_thumbnail(url=user.display_avatar.url if user.display_avatar else None)
    for qnum, ans in answers.items():
        embed.add_field(name=f"Q{qnum}", value=ans if len(ans) < 1024 else ans[:1021] + "...", inline=False)
    embed.set_footer(text=f"User ID: {user.id}")

    # Staff decision view
    class StaffDecisionView(View):
        def __init__(self, target_user_id: int, app_type: str, answers_dict: dict):
            super().__init__(timeout=None)
            self.target_user_id = target_user_id
            self.app_type = app_type
            self.answers = answers_dict

        @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, custom_id="app_accept")
        async def accept(self, interaction2: discord.Interaction, button: Button):
            staff_member = interaction2.user
            if not isinstance(staff_member, discord.Member) or not staff_member.guild_permissions.manage_guild:
                await interaction2.response.send_message("You don't have permission to use this.", ephemeral=True)
                return

            await interaction2.response.edit_message(content=f"Application accepted by {staff_member.display_name}.", embed=interaction2.message.embeds[0], view=None)

            # DM applicant
            try:
                applicant = await bot.fetch_user(self.target_user_id)
                await applicant.send(f"Your application was accepted by {staff_member.display_name}.")
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
                                await member.add_roles(role, reason=f"Application accepted by {staff_member}")
                            except discord.NotFound:
                                pass
                            except: pass
            except: pass

            # TEAM: send only the /create-team line to transactions channel
            if self.app_type == "team":
                try:
                    chan = bot.get_channel(TRANSACTIONS_CHANNEL_ID) or await bot.fetch_channel(TRANSACTIONS_CHANNEL_ID)
                    team_name = self.answers.get("1", "Unknown Team")
                    raw_color = self.answers.get("2", "").strip()
                    color = raw_color.lstrip("#")

                    if len(color) != 6 or any(c not in "0123456789abcdefABCDEF" for c in color):
                        try:
                            await interaction2.followup.send(f"Did not send team creation: hex color `{raw_color}` is invalid (must be 6 hex digits).", ephemeral=True)
                        except: pass
                        return

                    captain_mention = f"<@{self.target_user_id}>"
                    team_command = f'/create-team "{team_name}" {captain_mention} {color}'

                    # send only the command line
                    await chan.send(team_command)
                except: pass

        @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="app_deny")
        async def deny(self, interaction2: discord.Interaction, button: Button):
            staff_member = interaction2.user
            if not isinstance(staff_member, discord.Member) or not staff_member.guild_permissions.manage_guild:
                await interaction2.response.send_message("You don't have permission to use this.", ephemeral=True)
                return
            await interaction2.response.edit_message(content=f"Application denied by {staff_member.display_name}.", embed=interaction2.message.embeds[0], view=None)
            try:
                u = await bot.fetch_user(self.target_user_id)
                await u.send(f"Your application was denied by {staff_member.display_name}.")
            except: pass

    # send to review channel
    try:
        app_channel = bot.get_channel(APPLICATION_CHANNEL_ID) or await bot.fetch_channel(APPLICATION_CHANNEL_ID)
        view = StaffDecisionView(user.id, app_type, answers)
        await app_channel.send(embed=embed, view=view)
        await dm.send("Your application has been sent to staff.")
    except Exception:
        await dm.send("Error: application channel not configured or bot lacks permission to post. Contact an admin.")
        return

# ---------- on_ready & slash registration ----------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        tree = bot.tree
        guild_obj = discord.Object(id=GUILD_IDS) if isinstance(GUILD_IDS, int) else None

        @tree.command(name="register", description="Start an application (Caster / Ref / Commentator / Staff / Team)", guild=guild_obj)
        async def register_command(interaction: discord.Interaction):
            view = RegisterSelect()
            await interaction.response.send_message("Select application type:", view=view, ephemeral=True)

        if guild_obj:
            await tree.sync(guild=guild_obj)
        else:
            await tree.sync()
        print("Slash command registered.")
    except Exception as e:
        print("Failed to register command:", e)

bot.run(os.getenv("BOT_TOKEN"))
