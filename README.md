# gitrtc

## rtc component to git repository migration tool, with Django framework

## Credits: https://github.com/rtcTo/rtc2git

## Progress
  - The tool is good for changeset history collection and stream branching determine
  - The tool is good for the actual migration now

## Requirements
  - this intends to support only rtc v6+ (lscm show history returns a limit of 1000 items, the earlier version only return 100)
  - SCM tools (recommend lscm for performance, tune java heap size to 3G+ if you have large amount of changesets in streams)
  - python3 + Django + django-mptt + docutils
  - mysql + mysqlclient (optional, if your component has 10K+ changesets for performance consideration)
  - use ubuntu 14.04 / 16.04 x64 when doing the migration, with scmtools and IBM java 1.8
  
## Tested on
  - MacOs 10.12
  - ubuntu 14.04/16.04 (best)
  - RHEL 6
  - Docker (easy) https://hub.docker.com/r/lospringliu/gitrtc/
  
## Steps
  1. install scmtools and login with proper account as the alias rtc
    * lscm logout -r rtc
    * lscm login -r https://rtc/url -u your_account -P your_password -n rtc -c
    * lscm list connections  (you should see the line with something including repo/url and your_account)
    * lscm help  (see help information)
  2. install python3
  3. install python3 modules
    * pip3 install Django django-mptt docutils
    * pip3 install mysqlclient (if select to use mysql database)
  4. fork, clone and configure the tool
    * edit local_settings.py, you can specify your rtc information to automate login and relogin (rtc login / relogin works in shell environment, you might need change your password to make it work, confirm with cmd line test in step 1 above)
    * edit local_settings.py, you can configure your mail function
    * edit local_settings.py, COMPONENT_CREATORS provide information for the component creator info (by default I only figure out user name of the creator, but do not know the email, this variable provides this info)
    * edit local_settings.py to decide using sqlite or mysql for database backend.
  5. run the tool:
    * ./djangoapp.py --component component_name --streambase your_trunk_stream_for_the_component [--infoinit | --infoshow | --infoupdate | --inforeport | --migrate] [other options]
      * --infoinit (run only once, you should keep using fake component like 'init' and fake streambase like 'init_trunk')
        * retrieve all of your project areas
        * retrieve their related streams
        * retrieve components for each stream
        * usually you only need to do this once, result will be saved as rtc/fixtures/infoinit.json and will be loaded when you process other components
        * you only need to update this when you add/remove streams or modified components in streams
      * --infoshow [--streams[id1,id2,]] [--writehistory]
        * list streams with their ids that you can specify in options like --streams
        * --streams [id1,id2,]
          * show informations to a subset of streams
        * --writehistory
          * write changeset history of streams 
      * --infoupdate
        * list all of the baselines for the component
        * for each stream containing the component, do the following with streambase the first one to process
          * list and create tree of changeset for the stream (if show history return 1000 changeses(lscm limit), create History/history_stream_name file; we can not use compare here since there is squence differences)
          * list baselines with the corresponding changesets associated
          * determine branching point against streambase (you may need to do further compare for branches with common branching point on trunk, with --branchfurther --streamparent)
        * you can pickup new delivered changesets with --incremental
        * you can do a lightweight analysis to determine branching information with --shortcut_analyze
      * --inforeport [--withbaselines] [--withchangesets] [--streams [id1,id2,]] [--levelrange]
        * report rtc information and component specific numbers
          * --withchangesets
          show changeset information on branching points and ending points
          * --withbaselines
          show baseline information, help
          * --streams [id1,id2,...]
          limit the streams to show in the report if you have too many or you only interest in some of them
          * --levelrange [0,1000] --levelinterval 10
          used when --withchangesets
      * --migrate [--allstreams] [--streams [id1,id2]]
        * migrate only the trunk with --migrate only
        * you can migrate any streams using --streams [stream_id, stream_id2]
        * you can try to migrate all streams with --allstreams
        * you can use --incremental to pickup recently delivered changesets (collected already by --infoupdate --incremental)

## Examples
  1. ./djangoapp.py --component init --streambase init_trunk --infoinit  (only once)
    1. this generate rtc/fixtures/infoinit.json which will be loaded for each component you are going to migrate
  2. ./djangoapp.py --component yarn --streambase yarn_trunk --infoupdate
    1. ./djangoapp.py --component yarn --streambase yarn_trunk --infoupdate --branchfuther --streamparent yarn_IOP_working
      1. if all of you streams are directly cut from trunk, this step is not necessary
      2. if your branching if complicated, you would spend quite some time in this step
    2. ./djangoapp.py --component yarn --streambase yarn_trunk --infoupdate --incremental --streams [200]
      1. perform an update of stream with id 200, this will pickup any new baselines and changesets since last --infoupdate
  3. ./djangoapp.py --component yarn --streambase yarn_trunk --inforeport
    1. ./djangoapp.py --component yarn --streambase yarn_trunk --inforeport --withbaselines
    2. ./djangoapp.py --component yarn --streambase yarn_trunk --inforeport --withchangesets
    3. ./djangoapp.py --component yarn --streambase yarn_trunk --inforeport --withbaselines --withchangesets --streams [3,5,7]
  4. ./djangoapp.py --component yarn --streambase yarn_trunk --migrate (this migrate the trunk stream)
    1. ./djangoapp.py --component yarn --streambase yarn_trunk --migrate --streams [200]
      1. migrate a single stream whose id is 200
    2. ./djangoapp.py --component yarn --streambase yarn_trunk --migrate --allstreams
      1. tries to migrate all streams. If your stream relationship is complicated, you might need to run multiple times
    3. ./djangoapp.py --component yarn --streambase yarn_trunk --migrate --incremental
      1. perform an updated migration of trunk stream to git
    4. ./djangoapp.py --component yarn --streambase yarn_trunk --migrate --incremental --streams [200]
      1. perform an updated migration of stream with id 200 to git
