
## Notes for Installation and Dependencies

We make active use of newer Python 3.x features such as f-strings, so please use a more recent (I am writing this in Sept. 2020) version of Python if you're getting errors about unsupported features.

### Submodules
If you have an ssh key uploaded to GitHub, you should be able to simply run the "it handles everything" command
```
git submodule --init --recursive
```

If you do not have an ssh key uploaded and want to change the submodule URL to use (e.g.) HTTPS, then try the [following scheme](https://stackoverflow.com/questions/42028437/how-to-change-git-submodules-url-locally/42035018#:~:text=If%20you%20want%20to%20modify,that%20you%20want%20to%20push.&text=Then%20modify%20the%20.,the%20submodule%20URL%20as%20usual.)

First initialize the submodule configuration
```
git submodule init
```

Then go to `.git/config` (NOT `.gitmodules`) and edit the URL (for the submodule) to the form you want.

Finally run
```
git submodule update --recursive --remote
```
to pull through the new URL and establish the link.


### Requirements.txt

We are trying to maintain a dependency listing in requirements.txt.  You should be able to install all of these dependencies with the command
```
pip install -r requirements.txt
```


## Notes for Testing

To run the tests, simply type
```
pytest
```
in the root of the project

### Running Coverage Testing

To run pytest with coverage tests, execute
```
pytest --cov=SYS_ATL tests/
```
Then, if you want to see annotated source files, run
```
coverage html
```

