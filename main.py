import asyncio
import discord
from discord.ext import commands
from discord.ui import View, Select, Button
import os
import dotenv
from dotenv import load_dotenv

load_dotenv()


# ================== CONFIG ==================
GUILD_IDS = 1338455645896310784       # main guild where commands live
APPLICATION_CHANNEL_ID = 1509686940512030870  # channel where apps are posted

# Role IDs to give on acceptance
CASTER_ROLE_ID = 1338478126354923530
REF_ROLE_ID = 1356887381156036688
COMMENTATOR_ROLE_ID = 1346047919874248748

# App open/closed status (True = open, False = closed)
APP_STATUS = {
    "caster": True,
    "ref": True,
    "commentator": True,
}
# ============================================

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
            discord.SelectOption(label="Commentator", value="commentator", description="Apply to be a commentator")
        ]
        super().__init__(placeholder="Choose application type",
                         min_values=1, max_values=1,
                         options=options,
                         custom_id="register_select")

    async def callback(self, interaction: discord.Interaction):
        app_type = self.values[0]  # "caster" / "ref" / "commentator"

        # check open/closed
        if not APP_STATUS.get(app_type, True):
            await interaction.response.send_message("This App has been closed by a admin", ephemeral=True)
            return

        await interaction.response.send_message("Application Started — check your DMs.", ephemeral=True)
        await start_application_flow(interaction.user, app_type, interaction)

# ---------- Application flow ----------

async def start_application_flow(user: discord.User, app_type: str, interaction: discord.Interaction):
    # DM intro
    try:
        dm = await user.create_dm()
        await dm.send(
            "Application Started\n"
            "Please answer the questions below, either by selecting menu options or by sending messages to the bot."
        )
    except Exception:
        try:
            await interaction.followup.send(
                "I couldn't DM you. Please enable DMs from server members and try again.",
                ephemeral=True
            )
        except:
            pass
        return

    # collect text answer (required)
    async def collect_text(question: str) -> str:
        await dm.send(question)

        def check(m: discord.Message):
            return m.author.id == user.id and isinstance(m.channel, discord.DMChannel)

        try:
            msg = await bot.wait_for('message', timeout=300.0, check=check)
            content = msg.content.strip()
            if not content:
                await dm.send("Response cannot be empty. Please re-run /register.")
                raise asyncio.TimeoutError()
            return content
        except asyncio.TimeoutError:
            await dm.send("Timed out. Please re-run /register to start again.")
            raise

    # yes/no via select
    async def ask_yes_no(question: str) -> str:
        class YesNoView(View):
            def __init__(self):
                super().__init__(timeout=300)
                self.value = None

            @discord.ui.select(
                placeholder="Select Yes or No",
                min_values=1, max_values=1,
                options=[
                    discord.SelectOption(label="Yes", value="yes"),
                    discord.SelectOption(label="No", value="no")
                ]
            )
            async def select_callback(self, interaction2: discord.Interaction, select: Select):
                if interaction2.user.id != user.id:
                    await interaction2.response.send_message("This is not for you.", ephemeral=True)
                    return
                self.value = select.values[0]
                await interaction2.response.edit_message(
                    content=f"{question}\nAnswer: {self.value}",
                    view=None
                )
                self.stop()

        view = YesNoView()
        await dm.send(question, view=view)
        await view.wait()
        if view.value is None:
            await dm.send("Timed out. Please re-run /register to start again.")
            raise asyncio.TimeoutError()
        return view.value

    answers = {}

    # questions (no outer try here; each helper handles its own timeout)
    if app_type == "caster":
        answers["1"] = await collect_text("1/10. What is your Discord username & ID?")
        answers["2"] = await ask_yes_no("2/10. Do you have a mic?")
        answers["3"] = await collect_text("3/10. Do you have any past experience with casting in Gorilla Tag? If so please explain.")
        answers["4"] = await collect_text("4/10. Why do you want to become a Caster for MMM?")
        answers["5"] = await collect_text("5/10. What is your Upload & Download Speed? (use https://www.speedtest.net/)")
        answers["6"] = await collect_text("6/10. List your PC specifications.")
        answers["7"] = await collect_text("7/10. If you have past casting experience, link your YouTube/Twitch/etc.")
        answers["8"] = await collect_text("8/10. Are you familiar with OBS?")
        answers["9"] = await collect_text(
            "9/10. Please send a video showing OBS tasks (make Game Capture, add mic, import/export profile, make scene). "
            "Upload via Drive/MediaFire and send link."
        )
        answers["10"] = await collect_text("10/10. Any questions?")

    elif app_type == "ref":
        answers["1"] = await collect_text("1/11. What is your Discord username & ID?")
        answers["2"] = await collect_text("2/11. Name 3 official scrims you have reffed for (include teams and score).")
        answers["3"] = await collect_text("3/11. What is the recommended minimum time a ref should give late players?")
        answers["4"] = await collect_text("4/11. How long do runners have before taggers can pursue them?")
        answers["5"] = await collect_text("5/11. Where do runners go when tagged by the opposing team?")
        answers["6"] = await collect_text("6/11. What headsets are allowed in MMM official scrims?")
        answers["7"] = await collect_text("7/11. Can teams have different colors than teammates? If not, why?")
        answers["8"] = await collect_text("8/11. Do players have team abbreviation in their name while playing? If not, why?")
        answers["9"] = await ask_yes_no("9/11. Do you understand that if you don't ref at least 3-5 matches per season you may be removed/demoted?")
        answers["10"] = await ask_yes_no("10/11. Do you understand that bias may result in removal and potential server punishment?")
        answers["11"] = await ask_yes_no("11/11. Do you understand you must follow Head Referee instructions at all times?")

    elif app_type == "commentator":
        answers["1"] = await collect_text("1/5. What is your Discord username?")
        answers["2"] = await collect_text("2/5. Do you know in-game callouts and the league rules? Explain.")
        answers["3"] = await collect_text("3/5. Do you have experience commentating? If so, list the discords you worked for.")
        answers["4"] = await collect_text("4/5. Why should you be a commentator? Provide thorough reasoning.")
        answers["5"] = await collect_text("5/5. If you use a PC, what microphone do you use?")

    # Confirmation to user
    await dm.send("Application submitted.\nYour application has been submitted.")

    # Build embed
    embed = discord.Embed(
        title=f"{user.display_name}'s {app_type.capitalize()} Application",
        description="Application Submitted",
        color=0x2F3136
    )
    embed.set_thumbnail(url=user.display_avatar.url if user.display_avatar else None)
    for qnum, ans in answers.items():
        embed.add_field(
            name=f"Q{qnum}",
            value=ans if len(ans) < 1024 else ans[:1021] + "...",
            inline=False
        )
    embed.set_footer(text=f"User ID: {user.id}")

    # Staff view (with role-assign on accept)
    class StaffDecisionView(View):
        def __init__(self, target_user_id: int, app_type: str):
            super().__init__(timeout=None)
            self.target_user_id = target_user_id
            self.app_type = app_type

        @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, custom_id="app_accept")
        async def accept(self, interaction2: discord.Interaction, button: Button):
            staff_member = interaction2.user
            if not isinstance(staff_member, discord.Member) or not staff_member.guild_permissions.manage_guild:
                await interaction2.response.send_message("You don't have permission to use this.", ephemeral=True)
                return

            await interaction2.response.edit_message(
                content=f"Application accepted by {staff_member.display_name}.",
                embed=interaction2.message.embeds[0],
                view=None
            )

            # DM applicant
            try:
                applicant = await bot.fetch_user(self.target_user_id)
                await applicant.send(f"Your application was accepted by {staff_member.display_name}.")
            except:
                pass

            # give role
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

                    if role_id:
                        role = guild.get_role(role_id) or await guild.fetch_role(role_id)
                        if role:
                            try:
                                member = await guild.fetch_member(self.target_user_id)
                                await member.add_roles(role, reason=f"Application accepted by {staff_member}")
                            except discord.NotFound:
                                pass
                            except:
                                pass
            except:
                pass

        @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="app_deny")
        async def deny(self, interaction2: discord.Interaction, button: Button):
            staff_member = interaction2.user
            if not isinstance(staff_member, discord.Member) or not staff_member.guild_permissions.manage_guild:
                await interaction2.response.send_message("You don't have permission to use this.", ephemeral=True)
                return

            await interaction2.response.edit_message(
                content=f"Application denied by {staff_member.display_name}.",
                embed=interaction2.message.embeds[0],
                view=None
            )
            try:
                applicant = await bot.fetch_user(self.target_user_id)
                await applicant.send(f"Your application was denied by {staff_member.display_name}.")
            except:
                pass

    # send to review channel
    try:
        app_channel = bot.get_channel(APPLICATION_CHANNEL_ID) or await bot.fetch_channel(APPLICATION_CHANNEL_ID)
        view = StaffDecisionView(user.id, app_type)
        await app_channel.send(embed=embed, view=view)
        await dm.send("Your application has been sent to staff.")
    except Exception:
        await dm.send("Error: application channel not configured or bot lacks permission to post. Contact an admin.")
        return

# ---------- /manageapps command ----------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        tree = bot.tree

        # determine guild
        guild_obj = None
        if isinstance(GUILD_IDS, int):
            guild_obj = discord.Object(id=GUILD_IDS)
        elif isinstance(GUILD_IDS, (list, tuple)) and len(GUILD_IDS) > 0:
            guild_obj = discord.Object(id=GUILD_IDS[0])

        @tree.command(name="register", description="Start an application (Caster / Ref / Commentator)", guild=guild_obj)
        async def register_command(interaction: discord.Interaction):
            view = RegisterSelect()
            await interaction.response.send_message("Select application type:", view=view, ephemeral=True)

        @tree.command(name="manageapps", description="Open or close application types", guild=guild_obj)
        async def manageapps_command(interaction: discord.Interaction):
            if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("You must be an administrator to use this.", ephemeral=True)
                return

            class ManageSelect(Select):
                def __init__(self):
                    options = [
                        discord.SelectOption(label="Caster", value="caster", description="Manage Caster applications"),
                        discord.SelectOption(label="Referee", value="ref", description="Manage Referee applications"),
                        discord.SelectOption(label="Commentator", value="commentator", description="Manage Commentator applications"),
                    ]
                    super().__init__(placeholder="Choose which application to manage",
                                     min_values=1, max_values=1,
                                     options=options)

                async def callback(self, select_interaction: discord.Interaction):
                    if select_interaction.user.id != interaction.user.id:
                        await select_interaction.response.send_message("This is not for you.", ephemeral=True)
                        return

                    chosen = self.values[0]

                    class OpenCloseView(View):
                        def __init__(self, app_type: str):
                            super().__init__(timeout=60)
                            self.app_type = app_type

                        @discord.ui.button(label="Open", style=discord.ButtonStyle.green)
                        async def open_button(self, btn_interaction: discord.Interaction, button: Button):
                            if not isinstance(btn_interaction.user, discord.Member) or not btn_interaction.user.guild_permissions.administrator:
                                await btn_interaction.response.send_message("You must be an administrator to use this.", ephemeral=True)
                                return
                            APP_STATUS[self.app_type] = True
                            await btn_interaction.response.edit_message(
                                content=f"{self.app_type.capitalize()} applications are now **OPEN**.",
                                view=None
                            )

                        @discord.ui.button(label="Close", style=discord.ButtonStyle.red)
                        async def close_button(self, btn_interaction: discord.Interaction, button: Button):
                            if not isinstance(btn_interaction.user, discord.Member) or not btn_interaction.user.guild_permissions.administrator:
                                await btn_interaction.response.send_message("You must be an administrator to use this.", ephemeral=True)
                                return
                            APP_STATUS[self.app_type] = False
                            await btn_interaction.response.edit_message(
                                content=f"{self.app_type.capitalize()} applications are now **CLOSED**.\n"
                                        f"Users will see: `This App has been closed by a admin`",
                                view=None
                            )

                    status = "OPEN" if APP_STATUS.get(chosen, True) else "CLOSED"
                    oc_view = OpenCloseView(chosen)
                    await select_interaction.response.edit_message(
                        content=f"Managing **{chosen.capitalize()}** applications (currently **{status}**).\n"
                                f"Do you want to open or close it?",
                        view=oc_view
                    )

            view = View(timeout=120)
            view.add_item(ManageSelect())
            await interaction.response.send_message(
                "Select which application you want to manage:",
                view=view,
                ephemeral=True
            )

        # sync commands
        if guild_obj:
            await tree.sync(guild=guild_obj)
        else:
            await tree.sync()
        print("Slash commands registered.")
    except Exception as e:
        print("Failed to register commands:", e)

bot.run(os.getenv("BOT_TOKEN"))
