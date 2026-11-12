"""Public Season 10 observed leaderboard; stored data only, no independent polling."""
import asyncio
from datetime import date, timedelta, timezone
import hashlib
import io
import json
import logging
import math
import time

import discord
from .daily import database
from .daily_models import DailyReport
from .daily_timeline import load_font, player_color, row_names, ZONE
from utils.players.activity import verified_player
from utils.players.activity_models import RealmActivity
from utils.players.models import Player, utcnow

log = logging.getLogger(__name__)
PAGE_SIZE = 10
POST_DAY = date(1970, 1, 1)  # Reserved ledger date for the permanent all-time post.


def rankings(rows, now):
    """Union valid stored intervals per XUID, clipped to the observation cutoff."""
    groups = {}
    for xuid, start, end in rows:
        if xuid and start is not None and end is not None and start < min(end, now):
            groups.setdefault(xuid, []).append((start, min(end, now)))
    result = []
    for xuid, spans in groups.items():
        merged = []
        for start, end in sorted(spans):
            if merged and start <= merged[-1][1]:
                merged[-1] = merged[-1][0], max(end, merged[-1][1])
            else:
                merged.append((start, end))
        result.append((xuid, sum((b-a).total_seconds() for a,b in merged)))
    return sorted(result, key=lambda item: (-item[1], item[0]))


def hours_minutes(seconds):
    minutes = int(max(0, seconds)/60+0.5)
    return '<1m' if 0 < seconds < 60 else f'{minutes//60:,}h {minutes%60:02d}m'


def page_bounds(page, count):
    pages = max(1, math.ceil(count/PAGE_SIZE))
    return min(max(0, page), pages-1), pages


def render_page(data, page):
    from PIL import Image, ImageDraw
    rows, names, updated = data
    page, pages = page_bounds(page, len(rows))
    visible = rows[page*PAGE_SIZE:(page+1)*PAGE_SIZE]
    image = Image.new('RGB', (1200, 286+max(1,len(visible))*76), '#101a25')
    draw = ImageDraw.Draw(image)
    title, heading, regular, small = load_font(35,True), load_font(22,True), load_font(19), load_font(15)
    def fit(text, font, width):
        text = ' '.join(str(text).split())
        if draw.textlength(text,font=font) <= width:
            return text
        while text and draw.textlength(text+'…',font=font) > width:
            text=text[:-1]
        return text+'…'
    draw.rectangle((12,12,1187,image.height-13),outline='#304658',width=2)
    for x in (12,1180):
        draw.rectangle((x,12,x+7,19),fill='#f6b46d')
    draw.text((30,25),'COASTAL CRAFT · SEASON 10',font=regular,fill='#64cbe9')
    draw.text((30,58),'PLAYTIME LEADERBOARD',font=title,fill='#e3edf5')
    draw.text((30,104),'The Mighty Mesa Reborn · All-Time Observed Playtime',font=regular,fill='#afc5d7')
    stats = [(str(len(rows)), 'OBSERVED PLAYERS'),
             (hours_minutes(sum(total for _,total in rows)), 'COMBINED ACTIVITY'),
             (hours_minutes(rows[0][1] if rows else 0), 'TOP PLAYER')]
    for i,(value,label) in enumerate(stats):
        x=30+i*385
        draw.rectangle((x,146,x+370,220),fill='#1b2b39')
        draw.text((x+185,152),value,font=load_font(28,True),fill='#e3edf5',anchor='ma')
        draw.text((x+185,193),label,font=small,fill='#9eb6ca',anchor='ma')
    highest=rows[0][1] if rows else 1
    for i,(xuid,total) in enumerate(visible):
        rank=page*PAGE_SIZE+i+1
        y=236+i*76
        accent={1:'#e6bf63',2:'#bfcbd7',3:'#d6a17e'}.get(rank,'#9eb6ca')
        draw.rectangle((30,y,1169,y+68),fill='#1b2b39' if rank%2 else '#152331')
        draw.text((42,y+18),f'#{rank}',font=heading,fill=accent)
        first,second=row_names(xuid,names)
        draw.text((112,y+(9 if second else 21)),fit(first,heading,240),font=heading,fill='#e3edf5')
        if second:
            draw.text((112,y+37),fit(second,regular,240),font=regular,fill='#9eb6ca')
        draw.rectangle((372,y+26,1002,y+43),fill='#283949')
        draw.rectangle((372,y+26,372+max(1,630*total/highest),y+43),fill=player_color(xuid))
        draw.text((1154,y+21),hours_minutes(total),font=heading,fill='#e3edf5',anchor='ra')
    if not rows:
        draw.text((42,258),'No recorded observed activity is available for the configured Realm.',font=regular,fill='#afc5d7')
    draw.text((30,image.height-35),f'Page {page+1} of {pages} · Observed estimates; recorded coverage only',font=small,fill='#8fa7bb')
    stamp=updated.replace(tzinfo=timezone.utc).astimezone(ZONE).strftime('%b %d, %Y %I:%M %p %Z') if updated else 'unavailable'
    draw.text((1170,image.height-35),'Last activity update: '+stamp,font=small,fill='#8fa7bb',anchor='ra')
    output=io.BytesIO()
    image.save(output,format='PNG')
    return output.getvalue()


class LeaderboardController:
    def __init__(self,bot,runtime):
        self.bot,self.runtime=bot,runtime
        self.views=set()
        self.post_lock=asyncio.Lock()
        self.post_signatures={}
        self.post_view=None

    def start(self):
        self.post_view=PermanentLeaderboardView(self)
        self.bot.add_view(self.post_view)

    async def post(self,channel, *, create=True, data=None):
        guild=self.bot.settings['Coastal']
        if getattr(getattr(channel,'guild',None),'id',None)!=guild:
            raise ValueError('Choose a Coastal Craft text channel.')
        permissions=channel.permissions_for(channel.guild.me)
        if not all(getattr(permissions,key,False) for key in ('view_channel','read_message_history','send_messages','attach_files')):
            raise ValueError('I need View Channel, Read Message History, Send Messages, and Attach Files here.')
        async with self.post_lock:
            realm=self.runtime.config.selected_realm_id
            now=utcnow()
            def claim():
                if create:
                    row,_=DailyReport.get_or_create(guild=guild,channel=channel.id,realm=realm,day=POST_DAY)
                else:
                    row=DailyReport.get_or_none(guild=guild,channel=channel.id,realm=realm,day=POST_DAY)
                if row is None:
                    return None
                changed=DailyReport.update(lease=now+timedelta(minutes=3)).where(
                    (DailyReport.id==row.id)&((DailyReport.lease.is_null())|(DailyReport.lease<now))).execute()
                return DailyReport.get_by_id(row.id) if changed else None
            row=await database(claim)
            if row is None:
                raise ValueError('Leaderboard publication is already in progress; retry shortly.')
            try:
                async with asyncio.timeout(120):
                    marker='realm-leaderboard-'+hashlib.sha256(f'{guild}:{channel.id}:{realm}'.encode()).hexdigest()[:24]+'.png'
                    message=None
                    if row.message:
                        # Preserve deleted or inaccessible checkpoints rather than posting duplicates.
                        message=await channel.fetch_message(row.message)
                        if message.author.id!=self.bot.user.id or not any(a.filename==marker for a in message.attachments):
                            raise ValueError('Saved leaderboard message identity does not match.')
                    elif row.pending_since:
                        if now<row.pending_since+timedelta(minutes=5):
                            raise ValueError('An earlier send is being reconciled; retry after five minutes.')
                        async for candidate in channel.history(limit=None,oldest_first=True,
                                after=row.pending_since.replace(tzinfo=timezone.utc)-timedelta(minutes=1)):
                            if candidate.author.id==self.bot.user.id and any(a.filename==marker for a in candidate.attachments):
                                message=candidate
                                await database(lambda: DailyReport.update(message=message.id).where(DailyReport.id==row.id).execute())
                                break
                    data=data if data is not None else await self.load()
                    signature=LeaderboardView.digest(data)
                    if message and self.post_signatures.get(row.id)==signature:
                        return message.jump_url
                    if self.post_view is None:
                        self.post_view=PermanentLeaderboardView(self)
                    png=await asyncio.to_thread(render_page,data,0)
                    attachment=discord.File(io.BytesIO(png),filename=marker)
                    try:
                        if message:
                            await message.edit(attachments=[attachment],view=self.post_view,allowed_mentions=discord.AllowedMentions.none())
                        else:
                            await database(lambda: DailyReport.update(pending_since=utcnow()).where(DailyReport.id==row.id).execute())
                            message=await channel.send(file=attachment,view=self.post_view,allowed_mentions=discord.AllowedMentions.none())
                    finally:
                        attachment.close()
                    await database(lambda: DailyReport.update(message=message.id,signature=signature,pending_since=None).where(DailyReport.id==row.id).execute())
                    self.post_signatures[row.id]=signature
                    return message.jump_url
            finally:
                await database(lambda: DailyReport.update(lease=None).where(DailyReport.id==row.id).execute())

    async def load(self):
        realm=self.runtime.config.selected_realm_id
        def read():
            records=list(RealmActivity.select().where((RealmActivity.realm_id==realm) & (RealmActivity.status=='observed')))
            rows=rankings([(r.xuid,r.start,r.end) for r in records],utcnow())
            names,links={},{}
            for xuid,_ in rows:
                identity=verified_player(xuid)
                player=Player.get_or_none(Player.id==identity) if identity else None
                if player:
                    names[xuid]={'gamertag':player.gamertag or None}
                    if player.discord_id:
                        links[xuid]=(player.discord_id,player.discord_name)
            return rows,names,links,max((r.last_observed for r in records),default=None)
        rows,names,links,updated=await database(read)
        guild=self.bot.get_guild(self.bot.settings['Coastal'])
        cache=getattr(self.runtime.names,'entries',{}) if self.runtime.names else {}
        live=getattr(getattr(self.runtime.view,'activity',None),'data',None)
        live_names={p.xuid:p.name for p in getattr(live,'players',()) if p.name}
        for xuid,_ in rows:
            name=names.setdefault(xuid,{})
            cached=cache.get(xuid,{})
            name['gamertag']=name.get('gamertag') or live_names.get(xuid) or cached.get('name')
            if xuid in links:
                uid,stored=links[xuid]
                member=guild.get_member(uid) if guild else None
                name['discord']=member.display_name if member else stored
        return rows,names,updated

    async def open(self,interaction):
        data=await self.load()
        view=LeaderboardView(self,interaction.user.id,data)
        png=await view.png()
        with_file=discord.File(io.BytesIO(png),filename='realm-leaderboard.png')
        try:
            view.timeout=max(0.001,view.deadline-time.monotonic())
            view.message=await interaction.followup.send(file=with_file,view=view,wait=True,
                                                        allowed_mentions=discord.AllowedMentions.none())
            self.views.add(view)
        finally:
            with_file.close()

    async def refresh(self):
        active=[v for v in self.views if not v.is_finished() and time.monotonic()<v.deadline]
        try:
            posts=await database(lambda: list(DailyReport.select().where(
                (DailyReport.guild==self.bot.settings['Coastal']) &
                (DailyReport.realm==self.runtime.config.selected_realm_id) & (DailyReport.day==POST_DAY))))
            if not active and not posts:
                return
            data=await self.load()
        except Exception as error:
            log.warning('Leaderboard refresh unavailable (%s)',type(error).__name__)
            return
        for row in posts:
            try:
                channel=self.bot.get_channel(row.channel) or await self.bot.fetch_channel(row.channel)
                await self.post(channel,create=False,data=data)
            except Exception as error:
                log.warning('Permanent leaderboard refresh unavailable (%s)',type(error).__name__)
        for view in active:
            try:
                await view.update(data)
            except discord.HTTPException:
                self.views.discard(view)
                view.stop()
            except Exception as error:
                log.warning('Leaderboard page refresh unavailable (%s)',type(error).__name__)

    async def close(self):
        if self.post_view is not None:
            self.post_view.stop()
        for view in tuple(self.views):
            await view.on_timeout()


class PermanentLeaderboardView(discord.ui.View):
    def __init__(self,controller):
        super().__init__(timeout=None)
        self.controller=controller

    @discord.ui.button(label='Browse leaderboard',style=discord.ButtonStyle.secondary,
                       custom_id='captain:season10:leaderboard:browse')
    async def browse(self,interaction,button):
        guild=self.controller.bot.settings['Coastal']
        if interaction.guild_id!=guild:
            await interaction.response.send_message('Available in Coastal Craft only.',ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True,thinking=True)
        await self.controller.open(interaction)


class LeaderboardView(discord.ui.View):
    def __init__(self,controller,user_id,data):
        super().__init__(timeout=300)
        self.controller,self.user_id,self.data=controller,user_id,data
        self.deadline=time.monotonic()+300
        self.page=0
        self.cache={}
        self.message=None
        self.lock=asyncio.Lock()
        self.signature=self.digest(data)
        self.buttons()

    @staticmethod
    def digest(data):
        return hashlib.sha256(json.dumps(data,sort_keys=True,default=str).encode()).hexdigest()

    def buttons(self):
        self.page,pages=page_bounds(self.page,len(self.data[0]))
        self.previous.disabled=self.page==0
        self.next.disabled=self.page==pages-1

    async def interaction_check(self,interaction):
        if interaction.user.id!=self.user_id:
            await interaction.response.send_message('Only the member who opened this leaderboard can change its page.',ephemeral=True)
            return False
        remaining=self.deadline-time.monotonic()
        if remaining<=0:
            await interaction.response.send_message('This leaderboard navigation has expired. Run /realm leaderboard again.',ephemeral=True)
            return False
        self.timeout=remaining  # Button clicks never extend the original five-minute deadline.
        return True

    async def png(self):
        if self.page not in self.cache:
            self.cache[self.page]=await asyncio.to_thread(render_page,self.data,self.page)
        return self.cache[self.page]

    async def edit(self):
        attachment=discord.File(io.BytesIO(await self.png()),filename='realm-leaderboard.png')
        try:
            self.timeout=max(0.001,self.deadline-time.monotonic())
            await self.message.edit(attachments=[attachment],view=self,allowed_mentions=discord.AllowedMentions.none())
        finally:
            attachment.close()

    async def update(self,data):
        async with self.lock:
            if self.is_finished() or time.monotonic()>=self.deadline:
                return
            signature=self.digest(data)
            if signature==self.signature:
                return
            self.data=data
            self.cache.clear()
            self.buttons()
            await self.edit()
            self.signature=signature

    async def navigate(self,interaction,delta):
        await interaction.response.defer()
        async with self.lock:
            self.page+=delta
            self.buttons()
            try:
                await self.edit()
            except discord.HTTPException:
                self.controller.views.discard(self)
                self.stop()

    @discord.ui.button(label='Previous',style=discord.ButtonStyle.secondary)
    async def previous(self,interaction,button):
        await self.navigate(interaction,-1)

    @discord.ui.button(label='Next',style=discord.ButtonStyle.secondary)
    async def next(self,interaction,button):
        await self.navigate(interaction,1)

    async def on_timeout(self):
        async with self.lock:
            self.controller.views.discard(self)
            for item in self.children:
                item.disabled=True
            try:
                if self.message:
                    await self.message.edit(view=self)
            except discord.HTTPException:
                pass
            finally:
                self.stop()
