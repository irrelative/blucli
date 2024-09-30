# Some requests and responses

## /GitVersion
```
<version>4.6.3</version>
```


## /SyncStatus?timeout=10&etag=1800
After 10 seconds. Seems to block if there are no updates until timeout

```
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<SyncStatus icon="/images/players/N225_nt.png" db="-45.4" modelName="POWERNODE 2i" model="N225v2" brand="Bluesound" initialized="true" id="192.168.4.152:11000" mac="90:56:82:80:0F:D8" volume="13" name="family room Blu" etag="1800" schemaVersion="35" syncStat="1800" class="streamer-amplifier">
<zoneOptions>
  <option canHaveCentre="true" zoneMaster="true">front</option>
  <option zoneMaster="true">side</option>
</zoneOptions>
<pairWithSub/>
<bluetoothOutput/>
</SyncStatus>
```


## /Status
```
<status etag="87599d44fec52d24b67c7b71a044ebb0">
  <album>Dance Monkey</album>
  <artist>Tones and I</artist>
  <canMovePlayback>true</canMovePlayback>
  <canSeek>1</canSeek>
  <cursor>0</cursor>
  <db>-45.4</db>
  <fn>/var/mnt/nas2-MusicDownloaded/Singles/Tones and I - Dance Monkey.mp3</fn>
  <image>/Artwork?service=LocalMusic&fn=%2Fvar%2Fmnt%2Fnas2-MusicDownloaded%2F014.%20Tones%20and%20I%20-%20Dance%20Monkey.mp3</image>
  <indexing>0</indexing>
  <mid>963</mid>
  <mode>1</mode>
  <mute>0</mute>
  <name>Dance Monkey</name>
  <pid>8197</pid>
  <prid>0</prid>
  <quality>320000</quality>
  <repeat>2</repeat>
  <service>LocalMusic</service>
  <serviceIcon>/images/LibraryIcon.png</serviceIcon>
  <serviceName>Library</serviceName>
  <shuffle>0</shuffle>
  <sid>5</sid>
  <sleep/>
  <song>0</song>
  <state>pause</state>
  <streamFormat>MP3 320 kb/s</streamFormat>
  <syncStat>1800</syncStat>
  <title1>Dance Monkey</title1>
  <title2>Tones and I</title2>
  <title3>Dance Monkey</title3>
  <totlen>209</totlen>
  <volume>13</volume>
  <secs>32</secs>
</status>
```


## /ui/Configuration
Various UI endpoints, return XML that seems to represent full UI
```
<configuration>
    <item id="home" URI="/ui/Home"/>
    <item id="recentlyPlayed" URI="/ui/RecentlyPlayed"/>
    <item id="news" URI="/ui/News"/>
    <item id="favourites" URI="/ui/Favourites"/>
    <item id="sources" URI="/ui/Sources"/>
    <item id="search" URI="/ui/Search" withService="forService"/>
    <item id="nowPlayingContextMenu" URI="/ui/nowPlayingCM" resultType="contextMenu"/>
    <item id="queueItemContextMenu" URI="/ui/queueItemCM" resultType="contextMenu"/>
    <item id="resolveSoviURL" URI="/ui/resolveSoviURL"/>
</configuration>
```

## /Artwork?service=LocalMusic&fn=%2Fvar%2Fmnt%2Fnas2-MusicDownloaded%20Tones%20and%20I%20-%20Dance%20Monkey.mp3
Returns jpeg payload


## /Playlist?start=0&end=200
```
<playlist id="8197" modified="0" length="1">
    <song songid="15269" id="0" service="LocalMusic">
        <title>Dance Monkey</title>
        <art>Tones and I</art>
        <alb>Dance Monkey</alb>
        <fn>/var/mnt/nas2-MusicDownloaded/Singles/Tones and I - Dance Monkey.mp3</fn>
        <quality>320000</quality>
    </song>
</playlist>
```

## /Services
...huge list of options for all enabled services


## /RadioBrowse?service=Capture

```
<radiotime service="Capture">
    <item typeIndex="bluetooth-1" playerName="family room Blu" text="Bluetooth" inputType="bluetooth" id="input5" URL="Capture%3Abluez%3Abluetooth" image="/images/BluetoothIcon.png" type="audio"/>
    <item typeIndex="arc-1" playerName="family room Blu" text="HDMI frame tv" inputType="arc" id="input4" URL="Capture%3Ahw%3Aimxspdif%2C0%2F1%2F25%2F2%3Fid%3Dinput4" image="/images/capture/ic_tv.png" type="audio"/>
    <item typeIndex="analog-1" playerName="family room Blu" text="Plex Analog" inputType="analog" id="input0" URL="Capture%3Aplughw%3Aimxnadadc%2C0%2F44100%2F24%2F2%3Fid%3Dinput0" image="/images/capture/ic_analoginput.png" type="audio"/>
    <item playerName="family room Blu" text="Spotify" id="Spotify" URL="Spotify%3Aplay" image="/Sources/images/SpotifyIcon.png" serviceType="CloudService" type="audio"/>
</radiotime>
```