/*-------------------------------------------------------------------------*
 *---									---*
 *---		Pizza.java						---*
 *---									---*
 *---	    This file defines a class that keeps track of the		---*
 *---	ingredients of a pizza.						---*/

import		java.util.*;

class		Pizza
{
  //  I.  Constructor(s) and factory(s):
  //  PURPOSE:  To initialize 'this' to be an empty, default, pizza.
  //	No parameters.  No return value.
  public
  Pizza				()
  { }

  //  II.  Accessors:
  //  PURPOSE:  To return the dough source for 'this' Pizza.  No parameters.
  public
  DoughSource	getDoughSource	()
  {
    return(doughSource_);
  }

  //  PURPOSE:  To return the sauce on 'this' Pizza.  No parameters.
  public
  Sauce		getSauce	()
  {
    return(sauce_);
  }

  //  PURPOSE:  To return which ingredients are on top of the 'this' Pizza.
  public
  HashSet<Toppings>
		getToppingsDs	()
  {
    return(toppingsDs_);
  }


  //  III.  Mutators:
  //  PURPOSE:  To note that 'this' Pizza got dough from 'newDoughSource'.  No
  //	return value.
  public
  void		chooseDoughSource
  				(DoughSource	newDoughSource
				)
  {
    doughSource_	= newDoughSource;
  }


  //  PURPOSE:  To note that 'this' Pizza has sauce 'newSauce'.  No return
  //	value.
  public
  void		chooseSauce	(Sauce		newSauce
				)
  {
    sauce_	= newSauce;
  }


  //  PURPOSE:  To note that 'this' Pizza has topping 'newToppings'.
  //	No return value.
  public
  void		addToppings	(Toppings		newTopping
				)
  {
    toppingsDs_.add(newTopping);
  }


  //  IV.  Methods that do main and misc. work of class:
  //  PURPOSE:  To return a string representation of 'this'.  No parameters.
  public
  String	toString	()
  {
    StringBuilder	stringMe	= new StringBuilder();
    int			numToppings	= getToppingsDs().size();
    int			index;

    stringMe.append("pizza of ");

    stringMe.append(DOUGH_SOURCE_NAMES[getDoughSource().ordinal()]);
    stringMe.append(" dough");

    stringMe.append(" with ");
    stringMe.append(SAUCE_NAMES[getSauce().ordinal()]);
    stringMe.append(" sauce");

    if  (numToppings > 0)
    {
      Iterator<Toppings>	iter	= getToppingsDs().iterator();

      index			= 0;

      stringMe.append(" and topped with");

      do
      {
	if  (index == 0)
	{
	  stringMe.append(" ");
	}
	else
	if  ( (numToppings >= 2) && (index == (numToppings-1)) )
	{
	  stringMe.append(" and ");
	}
	else
	{
	  stringMe.append(", ");
	}

	stringMe.append(TOPPINGS_NAMES[iter.next().ordinal()]);
	index++;
      }
      while  (iter.hasNext());

    }

    return(stringMe.toString());
  }


  //  PURPOSE:  To add the results of 'other' into 'this'.  No return value.
  public
  void		combineWith	(Pizza	other)
  {
    if  (getDoughSource() == DoughSource.NONE)
    {
      doughSource_	= other.getDoughSource();
    }

    if  (getSauce() == Sauce.NONE)
    {
      sauce_		= other.getSauce();
    }

    for  (Toppings stack : other.getToppingsDs())
    {
      toppingsDs_.add(stack);
    }
  }

  //  V.  Member vars:
  //  PURPOSE:  To tell the source of the dough:
  private
  DoughSource			doughSource_	= DoughSource.NONE;

  //  PURPOSE:  To tell which sauce is on 'this' Pizza.
  private
  Sauce				sauce_		= Sauce.NONE;

  //  PURPOSE:  To tell which ingredients have been stacked on 'this' Pizza.
  private
  HashSet<Toppings>		toppingsDs_	= new HashSet<Toppings>();

  //  PURPOSE:  To hold the names of the dough sources.
  public
  static
  final
  String	DOUGH_SOURCE_NAMES[]
				= { "none",
				    "bought",
				    "made"
				  };

  //  PURPOSE:  To hold the names of the types of sauces.
  public
  static
  final
  String	SAUCE_NAMES[]	= { "none",
				    "tomato",
				    "pesto"
				  };

  //  PURPOSE:  To hold the names of toppings.
  public
  static
  final
  String	TOPPINGS_NAMES[]
				= { "none",
	  			    "cheese",
	  			    "mushrooms",
				    "spinach",
				    "pepperoni"
				  };

}
