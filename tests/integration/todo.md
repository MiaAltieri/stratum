Notes for claude for writing integration tests 

We will need a test directory. I do NOT want to have a test directory that exists permanently in the repo, this would be large make the Repo larger than it needs to be. Instead please create a fixture (?I am unsure if fixture is correct here?) that creates (and tears down) the test directory. The test directory should exist for all the tests and not be create for each test in the suite. Instead it should be created for the entire test suite ONCE. I would like to test directory to:
- have duplicate files
- have different levesl of depths (duplicates at different levels)
- have a variety of file types (not necessarily all but atleast 50% of the file types defined in the tagger)
- have files of a type we ignore 


For now I want to only test the happy path. There are a variety of tests I want for the happy path. 

Configs: 
- First configs work i.e.
    - directory depth
    - files to ignore
    - files of a certain size
    - one or more watch dirs 


Running + output
- Empty directory test

- Then I want to test does the suggestion log work
    - does it get created
    - can it be tailed 

- Test that the PID file gets created

- Does it actually note duplicates 

Suggested Deletions in separate dirs
- Please add a test that runs stratum 2x, one on dir-a, and one on dir-b. There should be duplicate files in both dir-a and dir-b. But since they are run separately they should not be reported to be deleted.

- Then have a test that runs dir-c (which contains dir-a and dir-b), this test should report the duplicates along with the suggested deletions. 