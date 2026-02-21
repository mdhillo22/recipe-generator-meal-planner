error id: file:///C:/Users/drsal/Downloads/hw1/csc-435-pa2-dsalcedo2/app-java/src/main/java/csc435/app/FileRetrievalEngine.java:_empty_/Array#length.
file:///C:/Users/drsal/Downloads/hw1/csc-435-pa2-dsalcedo2/app-java/src/main/java/csc435/app/FileRetrievalEngine.java
empty definition using pc, found symbol in pc: _empty_/Array#length.
empty definition using semanticdb
empty definition using fallback
non-local guesses:

offset: 279
uri: file:///C:/Users/drsal/Downloads/hw1/csc-435-pa2-dsalcedo2/app-java/src/main/java/csc435/app/FileRetrievalEngine.java
text:
```scala
package csc435.app;

public class FileRetrievalEngine 
{
    public static void main( String[] args )
    {
        int numWorkers;
        
        if (args.length == 0) {
            numWorkers = Runtime.getRuntime().availableProcessors();
        } else if (args.len@@gth == 1) {
            numWorkers = Integer.parseInt(args[0]);
        } else {
            System.err.println("Specify the number of worker threads as an argument");
            System.exit(1);
            return;
        }
        
        IndexStore store = new IndexStore();
        ProcessingEngine engine = new ProcessingEngine(store, numWorkers);
        AppInterface appInterface = new AppInterface(engine);

        appInterface.readCommands();
    }
}

```


#### Short summary: 

empty definition using pc, found symbol in pc: _empty_/Array#length.